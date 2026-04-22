"""
CSV persistence utility for the Prisoner's Dilemma simulation.

Writes round-by-round match data and aggregated metrics to .CSV files.
Used internally by the ManagerAgent to fulfill Component 2 §2.0.3:
"Persist results to .CSV storage."
"""

import csv
import os
from typing import Dict, List


class CSVWriter:
    """Utility class for persisting simulation results to CSV files."""

    @staticmethod
    def write_round_data(
        filepath: str,
        history: List[Dict],
        metrics: Dict,
        strategy_names: Dict[str, str] | None = None,
    ) -> None:
        """
        Write match history and aggregated metrics to a CSV file.

        Creates the output directory if it doesn't exist.

        Args:
            filepath: Path to the output CSV file.
            history: List of round records from Environment.get_state().history.
            metrics: Aggregated metrics dict from Environment.get_metrics().
            strategy_names: Optional dict mapping JID → strategy name for labeling.
        """
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        fieldnames = [
            "round",
            "p1_jid",
            "p1_strategy",
            "p1_action",
            "p2_jid",
            "p2_strategy",
            "p2_action",
            "p1_payoff",
            "p2_payoff",
            "p1_cumulative",
            "p2_cumulative",
        ]

        with open(filepath, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for record in history:
                row = {
                    "round": record["round"],
                    "p1_jid": record["p1_jid"],
                    "p1_strategy": (
                        strategy_names.get(record["p1_jid"], "unknown")
                        if strategy_names else "unknown"
                    ),
                    "p1_action": record["p1_action"],
                    "p2_jid": record["p2_jid"],
                    "p2_strategy": (
                        strategy_names.get(record["p2_jid"], "unknown")
                        if strategy_names else "unknown"
                    ),
                    "p2_action": record["p2_action"],
                    "p1_payoff": record["p1_payoff"],
                    "p2_payoff": record["p2_payoff"],
                    "p1_cumulative": record["p1_cumulative"],
                    "p2_cumulative": record["p2_cumulative"],
                }
                writer.writerow(row)

            # Write summary/metrics row
            if metrics:
                writer.writerow({})  # blank separator
                summary_writer = csv.writer(csvfile)
                summary_writer.writerow(["# AGGREGATED METRICS"])
                for key, value in metrics.items():
                    if isinstance(value, float):
                        summary_writer.writerow([f"# {key}", f"{value:.4f}"])
                    else:
                        summary_writer.writerow([f"# {key}", value])
