"""CLI entry point: python -m syft_enclaves.runner"""

# stdlib
import argparse
import logging

# relative
from syft_client.sync.syftbox_manager import SyftboxManager, SyftboxManagerConfig
from syft_enclaves.client import SyftEnclaveClient
from syft_enclaves.runner import EnclaveRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="Syft Enclave Runner")
    parser.add_argument("--email", required=True, help="Enclave datasite email")
    parser.add_argument(
        "--syftbox-folder",
        default=None,
        help="Path to SyftBox folder (default: ~/SyftBox)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="Seconds between poll cycles (default: 10)",
    )
    parser.add_argument(
        "--require-tee",
        action="store_true",
        help="Refuse to start if not running in a TEE",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    syftbox_folder = args.syftbox_folder or str(
        SyftboxManagerConfig.default_syftbox_folder()
    )
    config = SyftboxManagerConfig(
        syftbox_folder=syftbox_folder,
        email=args.email,
    )
    manager = SyftboxManager(config)
    client = SyftEnclaveClient(manager)

    runner = EnclaveRunner(
        client=client,
        poll_interval=args.poll_interval,
        require_tee=args.require_tee,
    )
    runner.run()


if __name__ == "__main__":
    main()
