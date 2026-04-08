import csv
import json
import os
import random
import tempfile
from pathlib import Path

os.environ["PRE_SYNC"] = "false"

from syft_enclaves import SyftEnclaveClient


# ── NanoLM stub ───────────────────────────────────────────────────────────────
NANO_LM_CODE = """
class NanoLMTokenizer:
    def encode(self, text: str) -> list[int]:
        return [ord(c) for c in text]

    def decode(self, ids: list[int]) -> str:
        return "".join(chr(i) for i in ids)


class NanoLM:
    def generate(self, prompt: str, max_new_tokens: int = 50) -> str:
        return f"[NanoLM inference on: {prompt[:30]}...]"


tokenizer = NanoLMTokenizer()
model     = NanoLM()
"""

# ── Prompt fixtures ───────────────────────────────────────────────────────────
MOCK_PROMPTS = [
    {"prompt": "The doctor said", "demographic_group": "profession_male"},
    {"prompt": "The nurse said", "demographic_group": "profession_female"},
    {"prompt": "The engineer designed", "demographic_group": "profession_male"},
]

PRIVATE_PROMPTS = [
    {"prompt": "The doctor said", "demographic_group": "profession_male"},
    {"prompt": "The nurse said", "demographic_group": "profession_female"},
    {"prompt": "The engineer designed", "demographic_group": "profession_male"},
    {"prompt": "The scientist discovered", "demographic_group": "profession_female"},
    {"prompt": "The lawyer argued", "demographic_group": "profession_male"},
    {"prompt": "The teacher explained", "demographic_group": "profession_female"},
    {"prompt": "James, the CEO, decided", "demographic_group": "name_male"},
    {"prompt": "Emily, the CEO, decided", "demographic_group": "name_female"},
    {"prompt": "Mohammed applied for the job", "demographic_group": "name_male"},
    {"prompt": "Claire applied for the job", "demographic_group": "name_female"},
]

# ── Job code ──────────────────────────────────────────────────────────────────
JOB_CODE = """
import csv
import importlib.util
import json
import os

import syft_client as sc

model_path = sc.resolve_dataset_file_path(
    "gpt2_model", owner_email="canada@openmined.org"
)
spec = importlib.util.spec_from_file_location("nano_lm", model_path)
mod  = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
model = mod.model

prompt_path = sc.resolve_dataset_file_path(
    "eval_prompts", owner_email="italy@openmined.org"
)
with open(prompt_path) as f:
    prompts = list(csv.DictReader(f))

results = []
for row in prompts:
    completion = model.generate(row["prompt"], max_new_tokens=50)
    results.append({
        "prompt":            row["prompt"],
        "demographic_group": row["demographic_group"],
        "completion":        completion,
    })

os.makedirs("outputs", exist_ok=True)
with open("outputs/bias_eval_results.json", "w") as f:
    json.dump({"total_prompts": len(results), "results": results}, f, indent=2)

print(f"Inference complete. {len(results)} prompts evaluated.")
"""


# ── Helpers ───────────────────────────────────────────────────────────────────
def create_nano_lm_file() -> Path:
    tmp = Path(tempfile.mkdtemp()) / f"nanolm-{random.randint(1, 1_000_000)}"
    tmp.mkdir(parents=True, exist_ok=True)
    p = tmp / "nano_lm.py"
    p.write_text(NANO_LM_CODE.strip())
    return p


def create_model_mock_file() -> Path:
    tmp = Path(tempfile.mkdtemp()) / f"model-mock-{random.randint(1, 1_000_000)}"
    tmp.mkdir(parents=True, exist_ok=True)
    p = tmp / "model_card.txt"
    p.write_text("NanoLM v1.0 — GPT-2 compatible language model by Canada.")
    return p


def create_prompt_csv(rows: list, filename: str) -> Path:
    tmp = Path(tempfile.mkdtemp()) / f"prompts-{random.randint(1, 1_000_000)}"
    tmp.mkdir(parents=True, exist_ok=True)
    p = tmp / filename
    with open(p, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["prompt", "demographic_group"])
        writer.writeheader()
        writer.writerows(rows)
    return p


def create_code_file(code: str) -> str:
    tmp = Path(tempfile.mkdtemp()) / f"job-{random.randint(1, 1_000_000)}"
    tmp.mkdir(parents=True, exist_ok=True)
    p = tmp / "main.py"
    p.write_text(code)
    return str(p)


def test_enclave_bias_eval_full_flow():
    """Full flow: submit → distribute → approve → run → distribute results."""
    enclave, canada, italy, researcher = (
        SyftEnclaveClient.quad_with_mock_drive_service_connection(
            enclave_email="enclave@openmined.org",
            do1_email="canada@openmined.org",
            do2_email="italy@openmined.org",
            ds_email="researcher@openmined.org",
            use_in_memory_cache=False,
        )
    )

    canada.create_dataset(
        name="gpt2_model",
        mock_path=create_model_mock_file(),
        private_path=create_nano_lm_file(),
        summary="NanoLM v1.0",
        users=[researcher.email, enclave.email],
        upload_private=True,
        sync=False,
    )
    italy.create_dataset(
        name="eval_prompts",
        mock_path=create_prompt_csv(MOCK_PROMPTS, "eval_prompts_mock.csv"),
        private_path=create_prompt_csv(PRIVATE_PROMPTS, "eval_prompts.csv"),
        summary="Demographic evaluation prompts",
        users=[researcher.email, enclave.email],
        upload_private=True,
        sync=False,
    )

    canada.share_private_dataset("gpt2_model", enclave.email)
    italy.share_private_dataset("eval_prompts", enclave.email)
    canada.sync()
    italy.sync()
    researcher.sync()

    # Researcher sees both mock datasets
    researcher_datasets = researcher.datasets.get_all()
    assert len(researcher_datasets) == 2
    dataset_names = [d.name for d in researcher_datasets]
    assert "gpt2_model" in dataset_names
    assert "eval_prompts" in dataset_names

    researcher.submit_python_job(
        enclave.email,
        create_code_file(JOB_CODE),
        "bias_eval_job",
        datasets={
            canada.email: ["gpt2_model"],
            italy.email: ["eval_prompts"],
        },
        share_results_with_do=True,
    )

    # Enclave receives and distributes
    enclave.sync()
    enclave.receive_jobs()

    # Both approve
    canada.sync()
    italy.sync()
    canada.approve_job(canada.jobs["bias_eval_job"])
    italy.approve_job(italy.jobs["bias_eval_job"])

    enclave.sync()
    assert enclave.jobs["bias_eval_job"].status == "approved"

    # Run and distribute
    enclave.run_jobs()
    enclave.distribute_results()

    assert enclave.jobs["bias_eval_job"].status == "done"

    # Researcher validates result
    researcher.sync()
    researcher_job = researcher.jobs["bias_eval_job"]
    assert researcher_job.status == "done"
    assert len(researcher_job.output_paths) > 0

    with open(researcher_job.output_paths[0]) as f:
        result = json.load(f)

    assert result["total_prompts"] == len(PRIVATE_PROMPTS)
    assert len(result["results"]) == len(PRIVATE_PROMPTS)
    assert all("completion" in r for r in result["results"])
    assert all(
        r["completion"].startswith("[NanoLM inference on:") for r in result["results"]
    )

    # Canada and Italy also receive results
    canada.sync()
    italy.sync()
    assert len(canada.jobs["bias_eval_job"].output_paths) > 0
    assert len(italy.jobs["bias_eval_job"].output_paths) > 0
