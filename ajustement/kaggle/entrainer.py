"""Ajustement de Qwen3-4B-Instruct-2507 pour l'agent Dalila (Kaggle, carte graphique T4 ; QLoRA avec Unsloth).

Entrée : le jeu privé fidamarzouk/dalila-ajustement (train.jsonl, val.jsonl, outils.json ; produit par
ajustement/generer.py). Sortie dans /kaggle/working : l'adaptateur LoRA et le modèle au format GGUF (q4_k_m), à charger
dans Ollama avec ajustement/Modelfile. Seules les réponses de l'assistant (appels d'outils et réponses) sont apprises ;
consignes, questions et résultats d'outils sont lus, jamais appris.
"""
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "unsloth"], check=True)

import glob, json, os
from unsloth import FastLanguageModel
from unsloth.chat_templates import train_on_responses_only
from datasets import Dataset
from trl import SFTConfig, SFTTrainer

ENTREE = os.path.dirname(glob.glob("/kaggle/input/**/train.jsonl", recursive=True)[0])
LONGUEUR = 6144  # consignes + outils ≈ 3 300 jetons, conversation ≈ 600

model, tok = FastLanguageModel.from_pretrained("unsloth/Qwen3-4B-Instruct-2507", max_seq_length=LONGUEUR,
                                               load_in_4bit=True)
model = FastLanguageModel.get_peft_model(
    model, r=16, lora_alpha=32, lora_dropout=0, bias="none", use_gradient_checkpointing="unsloth", random_state=7,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])

outils = json.load(open(f"{ENTREE}/outils.json", encoding="utf-8"))


def charger(nom):
    lignes = [json.loads(l) for l in open(f"{ENTREE}/{nom}.jsonl", encoding="utf-8")]
    textes = [tok.apply_chat_template(e["messages"], tools=outils, tokenize=False) for e in lignes]
    n = [len(tok(t).input_ids) for t in textes[:50]]
    print(nom, len(textes), "exemples ; jetons (50 premiers) max", max(n), "moyenne", sum(n) // len(n))
    return Dataset.from_dict({"text": textes})


train, val = charger("train"), charger("val")
print(train[0]["text"][-1500:])  # fin d'un exemple : appel d'outil, résultat, rappel, réponse

trainer = SFTTrainer(
    model=model, tokenizer=tok, train_dataset=train, eval_dataset=val,
    args=SFTConfig(dataset_text_field="text", max_seq_length=LONGUEUR, per_device_train_batch_size=1,
                   gradient_accumulation_steps=8, num_train_epochs=2, learning_rate=2e-4, lr_scheduler_type="cosine",
                   warmup_ratio=0.05, logging_steps=5, eval_strategy="steps", eval_steps=40, save_strategy="no",
                   optim="adamw_8bit", weight_decay=0.01, seed=7, output_dir="/kaggle/working/sorties", report_to="none",
                   fp16=True, bf16=False))
trainer = train_on_responses_only(trainer, instruction_part="<|im_start|>user\n",
                                  response_part="<|im_start|>assistant\n")
stats = trainer.train()
print(stats)
print("évaluation finale :", trainer.evaluate())

# vérification rapide : un exemple de validation, sans la réponse attendue
FastLanguageModel.for_inference(model)
e = json.loads(open(f"{ENTREE}/val.jsonl", encoding="utf-8").readline())
for coupe in (2, len(e["messages"]) - 1):  # 1) l'appel d'outil ; 2) la réponse finale
    p = tok.apply_chat_template(e["messages"][:coupe], tools=outils, tokenize=False, add_generation_prompt=True)
    ids = tok(p, return_tensors="pt").to("cuda")
    sortie = model.generate(**ids, max_new_tokens=120, do_sample=False)
    print("---", e["langue"], "| attendu :", json.dumps(e["messages"][coupe], ensure_ascii=False)[:300])
    print("    obtenu :", tok.decode(sortie[0][ids.input_ids.shape[1]:], skip_special_tokens=False)[:300])

model.save_pretrained("/kaggle/working/dalila_lora")
tok.save_pretrained("/kaggle/working/dalila_lora")
model.save_pretrained_gguf("/kaggle/working/dalila_gguf", tok, quantization_method="q4_k_m")
print(subprocess.run("ls -la /kaggle/working/dalila_gguf", shell=True, capture_output=True, text=True).stdout)
