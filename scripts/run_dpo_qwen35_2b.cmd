@echo off
cd /d C:\Users\User\Desktop\pulsar-ai
set PYTHONPATH=src
pulsar train configs/examples/cam-dpo-qwen3.5-2b.yaml --task dpo training.epochs=1 training.max_seq_length=384 > outputs\demo-logs\dpo_qwen35_2b.log 2>&1
