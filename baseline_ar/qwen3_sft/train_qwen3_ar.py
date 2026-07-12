"""
Fine-tune Qwen3-8B for addressee recognition (DIAM) with Unsloth + LoRA.

- bf16 LoRA by default (fits a 32GB RTX 5090); pass --load_in_4bit for smaller GPUs.
- Qwen3 "thinking" is disabled (enable_thinking=False) so the model behaves as a
  clean supervised classifier that emits only the JSON addressee set.
- Trains on assistant responses only (prompt tokens are masked).

Usage:
  python train_qwen3_ar.py --train_file data_sft/train.jsonl --out_dir outputs/qwen3-ar-lora
"""
import argparse

from unsloth import FastLanguageModel
from unsloth.chat_templates import train_on_responses_only
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="unsloth/Qwen3-8B")
    ap.add_argument("--train_file", default="data_sft/train.jsonl")
    ap.add_argument("--out_dir", default="outputs/qwen3-ar-lora")
    ap.add_argument("--max_seq_len", type=int, default=2048)
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--grad_accum", type=int, default=2)
    ap.add_argument("--lora_r", type=int, default=16)
    ap.add_argument("--lora_alpha", type=int, default=32)
    ap.add_argument("--load_in_4bit", action="store_true", help="use QLoRA (smaller GPUs)")
    ap.add_argument("--seed", type=int, default=3407)
    args = ap.parse_args()

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model,
        max_seq_length=args.max_seq_len,
        load_in_4bit=args.load_in_4bit,
        dtype=None,  # auto (bf16 on Ampere+/Blackwell)
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.0,
        bias="none",
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        use_gradient_checkpointing="unsloth",
        random_state=args.seed,
    )

    ds = load_dataset("json", data_files=args.train_file, split="train")

    def format_row(ex):
        text = tokenizer.apply_chat_template(
            ex["messages"],
            tokenize=False,
            add_generation_prompt=False,
            enable_thinking=False,
        )
        return {"text": text}

    ds = ds.map(format_row, remove_columns=[c for c in ds.column_names if c != "text"])

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=ds,
        args=SFTConfig(
            dataset_text_field="text",
            max_seq_length=args.max_seq_len,
            per_device_train_batch_size=args.batch,
            gradient_accumulation_steps=args.grad_accum,
            warmup_ratio=0.03,
            num_train_epochs=args.epochs,
            learning_rate=args.lr,
            logging_steps=10,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=args.seed,
            output_dir=args.out_dir,
            bf16=True,
            packing=False,  # required for response-only masking below
            report_to="none",
        ),
    )

    # Mask everything except the assistant response (Qwen chat markers).
    trainer = train_on_responses_only(
        trainer,
        instruction_part="<|im_start|>user\n",
        response_part="<|im_start|>assistant\n",
    )

    trainer.train()

    model.save_pretrained(args.out_dir)
    tokenizer.save_pretrained(args.out_dir)
    print(f"Saved LoRA adapter + tokenizer to {args.out_dir}")


if __name__ == "__main__":
    main()
