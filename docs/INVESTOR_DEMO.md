# Investor Demo Runbook

## Goal
Show a stable end-to-end product narrative without relying on live model training during the meeting.

## One-command startup (Windows)

```powershell
cd C:\Users\User\Desktop\pulsar-ai
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_investor_demo.ps1
```

Open:
- http://127.0.0.1:18088

What this command does:
1. Seeds deterministic demo data (experiments, prompts, datasets, workflow)
2. Reuses running UI if already started
3. Starts backend+UI on port 18088 otherwise

## Suggested live flow (10-12 min)

1. Dashboard
- Show total experiments, workflows, prompts, live system metrics.

2. Experiments
- Open `[DEMO] Qwen3.5-2B SFT Baseline`
- Open `[DEMO] Qwen3.5-2B DPO Aligned`
- Highlight better accuracy/F1 and lower loss after DPO.

3. Workflows
- Open `[DEMO] Banking AgentOffice`
- Click `Run`
- Explain role/risk/approval governance and agent interaction graph.

4. Prompt Lab
- Open `[DEMO] Credit Underwriting Prompt`
- Show version history and variable templating.

## Notes
- Workflow `Run` in this demo is orchestration simulation for UI node types (`data/agent/router/a2a/gateway`) and does not train a model.
- Real SFT/DPO training is available separately from `New Experiment` or CLI.

## Related
- See split-stand strategy: docs/STANDS.md


