@echo off
cd /d C:\Users\User\Desktop\pulsar-ai
set PYTHONPATH=src
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
set LOCAL_SNAPSHOT=C:\Users\User\.cache\huggingface\hub\models--Qwen--Qwen3.5-2B\snapshots\15852e8c16360a2fea060d615a32b45270f8a8fc
pulsar train configs/examples/cam-dpo-qwen3.5-2b.yaml --task dpo training.epochs=1 training.max_seq_length=384 model.name=%LOCAL_SNAPSHOT% model.name_full=%LOCAL_SNAPSHOT% > outputs\demo-logs\dpo_qwen35_2b_offline.log 2>&1
