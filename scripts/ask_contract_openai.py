import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from app.contract_qa import DEFAULT_CONTRACT_PATH, DEFAULT_MODEL, answer_contract_question

load_dotenv()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ask a question about a contract PDF using the OpenAI Responses API."
    )
    parser.add_argument(
        "question",
        help="Question to ask about the contract.",
    )
    parser.add_argument(
        "--contract",
        default=str(DEFAULT_CONTRACT_PATH),
        help="Path to the contract PDF.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="OpenAI model to use.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    contract_path = Path(args.contract)
    answer = answer_contract_question(
        question=args.question,
        model=args.model,
        contract_path=contract_path,
    )
    print(answer)


if __name__ == "__main__":
    main()
