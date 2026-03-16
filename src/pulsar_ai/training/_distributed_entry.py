"""Entry point for distributed training via accelerate launch.

This script is invoked by distributed.py and should not be called directly.
It loads the training config from a YAML file and runs SFT or DPO training.
"""

import argparse
import logging
import sys
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def main() -> None:
    """Parse args and run training."""
    parser = argparse.ArgumentParser(description="Distributed training entry point")
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to training config YAML.",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    task = config.get("task", "sft")
    logger.info("Distributed training: task=%s", task)

    if task == "sft":
        from pulsar_ai.training.sft import train_sft

        results = train_sft(config)
    elif task == "dpo":
        from pulsar_ai.training.dpo import train_dpo

        results = train_dpo(config)
    else:
        logger.error("Unknown task: %s", task)
        sys.exit(1)

    logger.info("Training complete: %s", results)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
