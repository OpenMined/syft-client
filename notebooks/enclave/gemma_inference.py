"""Gemma 3 IT — Flax Inference Module

Standalone inference engine for Gemma 3 instruction-tuned models using Flax.
Module hierarchy mirrors google-deepmind/gemma so checkpoint param names map
1:1 to Flax sub-module names.

Supports: 270m, 1b, 4b, 12b, 27b.

Adapted from: github.com/anthropics/beach-notebooks/gemma/local_PoC.py
"""

import os
import time

import jax
import jax.numpy as jnp
import orbax.checkpoint as ocp
import sentencepiece as spm
from flax import linen as nn


# ── Model configs ───────────────────────────────────────────────────────────
MODEL_CONFIGS = {
    "270m": dict(num_layers=18, embed_dim=640,  hidden_dim=2048,  num_heads=4,  num_kv_heads=1,  head_dim=256, sliding_window=512,  kaggle_handle="google/gemma-3/flax/gemma-3-270m-it", ckpt_subdir="gemma-3-270m-it"),
    "1b":   dict(num_layers=26, embed_dim=1152, hidden_dim=6912,  num_heads=4,  num_kv_heads=1,  head_dim=256, sliding_window=512,  kaggle_handle="google/gemma-3/flax/gemma3-1b-it",    ckpt_subdir="gemma3-1b-it"),
    "4b":   dict(num_layers=34, embed_dim=2560, hidden_dim=10240, num_heads=8,  num_kv_heads=4,  head_dim=256, sliding_window=1024, kaggle_handle="google/gemma-3/flax/gemma3-4b-it",    ckpt_subdir="gemma3-4b-it"),
    "12b":  dict(num_layers=48, embed_dim=3840, hidden_dim=15360, num_heads=16, num_kv_heads=8,  head_dim=256, sliding_window=1024, kaggle_handle="google/gemma-3/flax/gemma3-12b-it",   ckpt_subdir="gemma3-12b-it"),
    "27b":  dict(num_layers=62, embed_dim=5376, hidden_dim=21504, num_heads=32, num_kv_heads=16, head_dim=128, sliding_window=1024, kaggle_handle="google/gemma-3/flax/gemma3-27b-it",   ckpt_subdir="gemma3-27b-it"),
}

# ── Architecture constants (set by set_model_config) ───────────────────────
NUM_LAYERS       = 18
EMBED_DIM        = 640
HIDDEN_DIM       = 2048
NUM_HEADS        = 4
NUM_KV_HEADS     = 1
HEAD_DIM         = 256
VOCAB_SIZE       = 262144
SLIDING_WINDOW   = 512
LOCAL_ROPE_BASE  = 10_000
GLOBAL_ROPE_BASE = 1_000_000
ATTN_TYPES       = (('local',) * 5 + ('global',)) * 3

K_MASK = -2.3819763e38  # Google's masking constant (≈ float32 -inf)


def set_model_config(size):
    """Set module-level architecture constants from a model config."""
    global NUM_LAYERS, EMBED_DIM, HIDDEN_DIM, NUM_HEADS, NUM_KV_HEADS
    global HEAD_DIM, SLIDING_WINDOW, ATTN_TYPES
    cfg = MODEL_CONFIGS[size]
    NUM_LAYERS     = cfg['num_layers']
    EMBED_DIM      = cfg['embed_dim']
    HIDDEN_DIM     = cfg['hidden_dim']
    NUM_HEADS      = cfg['num_heads']
    NUM_KV_HEADS   = cfg['num_kv_heads']
    HEAD_DIM       = cfg['head_dim']
    SLIDING_WINDOW = cfg['sliding_window']
    pattern = ('local',) * 5 + ('global',)
    ATTN_TYPES = (pattern * ((NUM_LAYERS + 5) // 6))[:NUM_LAYERS]
    return cfg


# ── Standalone helpers ────────────────────────────────────────────────────

def apply_rope(x, positions, base_freq):
    """Rotary position embeddings (split-half rotation)."""
    half = x.shape[-1] // 2
    freq_exp = (2.0 / x.shape[-1]) * jnp.arange(half, dtype=jnp.float32)
    timescale = base_freq ** freq_exp
    angles = positions[..., None, None] / timescale
    sin, cos = jnp.sin(angles), jnp.cos(angles)
    x1, x2 = x[..., :half], x[..., half:]
    return jnp.concatenate([x1 * cos - x2 * sin,
                            x2 * cos + x1 * sin], axis=-1)


def make_masks(seq_len):
    """Causal masks — local layers also clip to a sliding window."""
    causal = jnp.tril(jnp.ones((seq_len, seq_len), dtype=jnp.bool_))
    window = jnp.triu(jnp.ones((seq_len, seq_len), dtype=jnp.bool_),
                      k=-(SLIDING_WINDOW - 1))
    return {
        'local':  (causal & window)[None, None],
        'global': causal[None, None],
    }


def make_decode_masks(pos):
    """Masks for single-token decode."""
    total_len = pos + 1
    positions = jnp.arange(total_len)
    return {
        'local':  (positions >= pos - SLIDING_WINDOW + 1)[None, None, None, :],
        'global': jnp.ones((1, 1, 1, total_len), dtype=jnp.bool_),
    }


# ── Flax modules ───────────────────────────────────────────────────────────

def _get(module, name):
    """Read a pre-loaded param without shape checking."""
    return module.variable('params', name, lambda: None).value


class Einsum(nn.Module):
    @nn.compact
    def __call__(self, equation, x):
        return jnp.einsum(equation, x, _get(self, 'w'))


class RMSNorm(nn.Module):
    @nn.compact
    def __call__(self, x):
        scale = _get(self, 'scale')
        var = jnp.mean(jnp.square(x), axis=-1, keepdims=True)
        return x * jax.lax.rsqrt(var + 1e-6) * (1 + scale)


class Attention(nn.Module):
    @nn.compact
    def __call__(self, x, positions, mask, attn_type, cache=None):
        q  = Einsum(name='q_einsum')('bsd,ndh->bsnh', x)
        kv = Einsum(name='kv_einsum')('bsd,ckdh->cbskh', x)
        k, v = kv[0], kv[1]

        q = RMSNorm(name='_query_norm')(q)
        k = RMSNorm(name='_key_norm')(k)

        base = LOCAL_ROPE_BASE if attn_type == 'local' else GLOBAL_ROPE_BASE
        q = apply_rope(q, positions, base)
        k = apply_rope(k, positions, base)

        if cache is not None:
            cached_k, cached_v = cache
            k = jnp.concatenate([cached_k, k], axis=1)
            v = jnp.concatenate([cached_v, v], axis=1)
        new_cache = (k, v)

        q = q * (HEAD_DIM ** -0.5)

        k_exp = jnp.repeat(k, NUM_HEADS // NUM_KV_HEADS, axis=2)
        v_exp = jnp.repeat(v, NUM_HEADS // NUM_KV_HEADS, axis=2)

        logits = jnp.einsum('bsnh,btnh->bnst', q, k_exp)
        logits = jnp.where(mask, logits, K_MASK)
        weights = jax.nn.softmax(logits, axis=-1)

        out = jnp.einsum('bnst,btnh->bsnh', weights, v_exp)
        return Einsum(name='attn_vec_einsum')('bsnh,nhd->bsd', out), new_cache


class FeedForward(nn.Module):
    @nn.compact
    def __call__(self, x):
        gate = Einsum(name='gating_einsum')('bsf,nhf->bsnh', x)
        h = jax.nn.gelu(gate[:, :, 0, :]) * gate[:, :, 1, :]
        return Einsum(name='linear')('bsh,hf->bsf', h)


class Block(nn.Module):
    attn_type: str = 'local'

    @nn.compact
    def __call__(self, x, positions, mask, cache=None):
        h = RMSNorm(name='pre_attention_norm')(x)
        h, new_cache = Attention(name='attn')(h, positions, mask, self.attn_type, cache)
        h = RMSNorm(name='post_attention_norm')(h)
        x = x + h
        h = RMSNorm(name='pre_ffw_norm')(x)
        h = FeedForward(name='mlp')(h)
        h = RMSNorm(name='post_ffw_norm')(h)
        return x + h, new_cache


class Embedder(nn.Module):
    @nn.compact
    def __call__(self, token_ids):
        table = _get(self, 'input_embedding')
        return table[token_ids] * jnp.sqrt(float(EMBED_DIM)), table


class Transformer(nn.Module):
    @nn.compact
    def __call__(self, tokens, cache=None):
        x, embed_table = Embedder(name='embedder')(tokens)

        if cache is None:
            seq_len = tokens.shape[1]
            positions = jnp.arange(seq_len)[None, :]
            masks = make_masks(seq_len)
        else:
            cache_len = cache['layer_0'][0].shape[1]
            positions = jnp.array([[cache_len]])
            masks = make_decode_masks(cache_len)

        new_cache = {}
        for i in range(NUM_LAYERS):
            layer_cache = cache[f'layer_{i}'] if cache is not None else None
            x, layer_new_cache = Block(attn_type=ATTN_TYPES[i], name=f'layer_{i}')(
                x, positions, masks[ATTN_TYPES[i]], layer_cache
            )
            new_cache[f'layer_{i}'] = layer_new_cache

        x = RMSNorm(name='final_norm')(x)
        logits = x @ embed_table.T
        return logits, new_cache


# ── Weight loading ─────────────────────────────────────────────────────────

def nestify(flat):
    """Convert Orbax flat dict to nested dict for Flax."""
    nested = {}
    for flat_key, param_dict in flat.items():
        parts = flat_key.split('/')
        d = nested
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = param_dict
    return nested


def load_params(weights_dir, cfg):
    """Load Orbax checkpoint and return Flax-compatible params dict."""
    ckpt_path = os.path.join(weights_dir, cfg['ckpt_subdir'])
    raw = ocp.PyTreeCheckpointer().restore(ckpt_path)
    return {'params': nestify(raw)['transformer']}


# ── Tokenizer + generation ─────────────────────────────────────────────────

def load_tokenizer(weights_dir):
    """Load SentencePiece tokenizer from weights directory."""
    sp = spm.SentencePieceProcessor()
    sp.Load(os.path.join(weights_dir, 'tokenizer.model'))
    return sp


def format_chat(prompt):
    """Wrap prompt in Gemma's chat template."""
    return f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"


def sample_token(logits, temperature=0.8, top_k=40):
    """Temperature-scaled top-k sampling. Greedy when temperature=0."""
    if temperature == 0:
        return int(jnp.argmax(logits))
    logits = logits / temperature
    top_k_logits, top_k_ids = jax.lax.top_k(logits, top_k)
    probs = jax.nn.softmax(top_k_logits)
    idx = jax.random.categorical(
        jax.random.PRNGKey(int(jnp.sum(logits) * 1e6) % 2**31),
        jnp.log(probs),
    )
    return int(top_k_ids[idx])


def generate(model, params, sp, prompt, max_new_tokens=200, temperature=0.8, top_k=40):
    """Autoregressive generation with KV cache and chat template.

    Returns (response_text, stats_dict).
    """
    chat_input = format_chat(prompt)
    token_ids = [sp.bos_id()] + sp.EncodeAsIds(chat_input)
    prompt_tokens = jnp.array([token_ids], dtype=jnp.int32)
    prompt_text = sp.Decode(token_ids)
    generated_ids = list(token_ids)

    t_prefill = time.time()
    logits, cache = model.apply(params, prompt_tokens)
    ttft = time.time() - t_prefill

    t_decode = time.time()
    decode_tokens = 0

    for _ in range(max_new_tokens):
        next_id = sample_token(logits[0, -1], temperature, top_k)
        if next_id == sp.eos_id():
            break

        prev_text = sp.Decode(generated_ids)
        generated_ids.append(next_id)
        new_text = sp.Decode(generated_ids)

        response_so_far = new_text[len(prompt_text):]
        if '<end_of_turn>' in response_so_far:
            break

        decode_tokens += 1
        logits, cache = model.apply(
            params, jnp.array([[next_id]], dtype=jnp.int32), cache=cache
        )

    decode_elapsed = time.time() - t_decode
    decode_tps = decode_tokens / decode_elapsed if decode_elapsed > 0 else 0

    full = sp.Decode(generated_ids)
    response_start = full.find('<start_of_turn>model\n')
    if response_start != -1:
        response = full[response_start + len('<start_of_turn>model\n'):]
        response = response.replace('<end_of_turn>', '').strip()
    else:
        response = full

    stats = {
        'ttft': ttft,
        'decode_tps': decode_tps,
        'decode_tokens': decode_tokens,
        'decode_elapsed': decode_elapsed,
        'prompt_tokens': len(token_ids),
    }
    return response, stats
