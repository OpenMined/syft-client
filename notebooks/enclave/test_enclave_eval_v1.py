"""Enclave eval — v1 experiment: weights vs. inference-code split.

A variant of ``test_enclave_eval.py``. The two data owners stay, but the model
is split differently:

- **Canada** contributes the model **weights** — a passive data file
  (parameters), not executable code.
- **Italy** contributes the evaluation prompts.
- The **data scientist's job code contains the inference code** — the model
  implementation itself. The job loads Canada's weights and Italy's prompts and
  runs inference.

In ``test_enclave_eval.py`` Canada shipped ``nano_lm.py`` — the model *code*.
Here the model code lives with the data scientist; the data owner ships only
weights.
"""

import csv
import json
import os
import random
import tempfile
from pathlib import Path

os.environ["PRE_SYNC"] = "false"

from syft_enclaves import SyftEnclaveClient


# ── Canada's model weights — a passive data file, not code ────────────────────
MODEL_WEIGHTS = {
    "model_name": "NanoLM",
    "version": "1.0",
    "vocab_size": 256,
}

# ── Italy's evaluation prompts ────────────────────────────────────────────────
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

# ── Job code — submitted by the data scientist ────────────────────────────────
# The model implementation (inference code) lives HERE. It loads Canada's
# weights and Italy's prompts, then runs inference.
JOB_CODE = """
import csv
import json
import os

import syft_client as sc


# Inference code (the model implementation) — written by the data scientist.
# The weights come from the data owner; this code knows how to use them.
class NanoLM:
    def __init__(self, weights):
        self.weights = weights

    def generate(self, prompt):
        name = self.weights.get("model_name", "model")
        return f"[{name} inference on: {prompt[:30]}...]"


# Load model weights from Canada's private dataset
weights_path = sc.resolve_dataset_file_path(
    "model_weights", owner_email="canada@openmined.org"
)
with open(weights_path) as f:
    weights = json.load(f)
model = NanoLM(weights)

# Load evaluation prompts from Italy's private dataset
prompt_path = sc.resolve_dataset_file_path(
    "eval_prompts", owner_email="italy@openmined.org"
)
with open(prompt_path) as f:
    prompts = list(csv.DictReader(f))

# Run inference
results = []
for row in prompts:
    completion = model.generate(row["prompt"])
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
def create_model_weights_file() -> Path:
    """Write the model weights to a JSON file — Canada's private dataset."""
    tmp = Path(tempfile.mkdtemp()) / f"weights-{random.randint(1, 1_000_000)}"
    tmp.mkdir(parents=True, exist_ok=True)
    p = tmp / "weights.json"
    p.write_text(json.dumps(MODEL_WEIGHTS, indent=2))
    return p


def create_model_mock_file() -> Path:
    """Write a plain-text model card — the mock (public) side of Canada's dataset."""
    tmp = Path(tempfile.mkdtemp()) / f"model-mock-{random.randint(1, 1_000_000)}"
    tmp.mkdir(parents=True, exist_ok=True)
    p = tmp / "model_card.txt"
    p.write_text("NanoLM v1.0 - GPT-2 compatible language model weights by Canada.")
    return p


def create_prompt_csv(rows: list, filename: str) -> Path:
    """Write evaluation prompts to a CSV file — Italy's dataset."""
    tmp = Path(tempfile.mkdtemp()) / f"prompts-{random.randint(1, 1_000_000)}"
    tmp.mkdir(parents=True, exist_ok=True)
    p = tmp / filename
    with open(p, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["prompt", "demographic_group"])
        writer.writeheader()
        writer.writerows(rows)
    return p


def create_code_file(code: str) -> str:
    """Write job code to a temp file."""
    tmp = Path(tempfile.mkdtemp()) / f"job-{random.randint(1, 1_000_000)}"
    tmp.mkdir(parents=True, exist_ok=True)
    p = tmp / "main.py"
    p.write_text(code)
    return str(p)


def test_enclave_eval_v1_weights_and_code_split():
    """Canada provides model weights, Italy provides prompts, the DS provides
    the inference code in the job — the job loads both and runs inference."""
    enclave, canada, italy, researcher = (
        SyftEnclaveClient.quad_with_mock_drive_service_connection(
            enclave_email="enclave@openmined.org",
            do1_email="canada@openmined.org",
            do2_email="italy@openmined.org",
            ds_email="researcher@openmined.org",
            use_in_memory_cache=False,
        )
    )

    # Canada contributes model WEIGHTS (a passive data file, not code).
    canada.create_dataset(
        name="model_weights",
        mock_path=create_model_mock_file(),
        private_path=create_model_weights_file(),
        summary="NanoLM v1.0 model weights (parameters)",
        users=[researcher.email, enclave.email],
        upload_private=True,
        sync=False,
    )
    # Italy contributes the evaluation prompts.
    italy.create_dataset(
        name="eval_prompts",
        mock_path=create_prompt_csv(MOCK_PROMPTS, "eval_prompts_mock.csv"),
        private_path=create_prompt_csv(PRIVATE_PROMPTS, "eval_prompts.csv"),
        summary="Demographic evaluation prompts",
        users=[researcher.email, enclave.email],
        upload_private=True,
        sync=False,
    )

    canada.share_private_dataset("model_weights", enclave.email)
    italy.share_private_dataset("eval_prompts", enclave.email)
    canada.sync()
    italy.sync()
    researcher.sync()

    # Researcher sees both mock datasets.
    researcher_datasets = researcher.datasets.get_all()
    assert len(researcher_datasets) == 2
    dataset_names = {d.name for d in researcher_datasets}
    assert dataset_names == {"model_weights", "eval_prompts"}

    # Researcher submits the job — the inference code is inside JOB_CODE.
    researcher.submit_python_job(
        enclave.email,
        create_code_file(JOB_CODE),
        "bias_eval_job",
        datasets={
            canada.email: ["model_weights"],
            italy.email: ["eval_prompts"],
        },
        share_results_with_do=True,
    )

    # Enclave receives and distributes.
    enclave.sync()
    enclave.receive_jobs()

    # Both data owners approve.
    canada.sync()
    italy.sync()
    canada.approve_job(canada.jobs["bias_eval_job"])
    italy.approve_job(italy.jobs["bias_eval_job"])

    enclave.sync()
    assert enclave.jobs["bias_eval_job"].status == "approved"

    # Run and distribute.
    enclave.run_jobs()
    enclave.distribute_results()

    assert enclave.jobs["bias_eval_job"].status == "done"

    # Researcher validates the result.
    researcher.sync()
    researcher_job = researcher.jobs["bias_eval_job"]
    assert researcher_job.status == "done"
    assert len(researcher_job.output_paths) > 0

    with open(researcher_job.output_paths[0]) as f:
        result = json.load(f)

    assert result["total_prompts"] == len(PRIVATE_PROMPTS)
    assert len(result["results"]) == len(PRIVATE_PROMPTS)
    assert all("completion" in r for r in result["results"])
    # The model name comes from Canada's weights — proof the weights flowed
    # through the data-scientist-supplied inference code.
    assert all(
        r["completion"].startswith("[NanoLM inference on:") for r in result["results"]
    )

    # Canada and Italy also receive the result.
    canada.sync()
    italy.sync()
    assert len(canada.jobs["bias_eval_job"].output_paths) > 0
    assert len(italy.jobs["bias_eval_job"].output_paths) > 0
