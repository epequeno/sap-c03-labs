"""CDK app for the SAP-C03 labs.

One stack exists at a time, chosen with `-c lab=NN`, so every lab is
independently deployable and independently destroyable. Only labs whose
stack module has been written are registered: an unknown `lab` value fails
loudly with the list of what does exist.

Every resource inherits four tags from the app, which is what the evidence
and teardown scripts query.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import aws_cdk as cdk

from stacks.lab02_multitenant_api import Lab02MultitenantApi

PROJECT = "sap-c03-labs"
OWNER = os.environ.get("SAP_LABS_OWNER", "steven")
DEFAULT_REGION = os.environ.get("CDK_DEFAULT_REGION", "us-east-1")

# Registered labs. Add the import and the entry together.
STACKS: dict[str, type[cdk.Stack]] = {
    "02": Lab02MultitenantApi,
}


def main() -> None:
    app = cdk.App()

    lab = str(app.node.try_get_context("lab") or "02")
    if lab not in STACKS:
        available = ", ".join(sorted(STACKS))
        print(
            f"lab={lab!r} has no stack yet. Registered: {available}. "
            f"Write infra/stacks/lab{lab}_*.py and register it in infra/app.py.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    tear_down = app.node.try_get_context("tearDown") or str(date.today() + timedelta(days=1))

    stack = STACKS[lab](
        app,
        f"SapC03Lab{lab}",
        env=cdk.Environment(
            account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
            region=os.environ.get("CDK_DEFAULT_REGION", DEFAULT_REGION),
        ),
        description=f"SAP-C03 exam lab {lab}. Disposable: tear down the same day.",
    )

    cdk.Tags.of(stack).add("Project", PROJECT)
    cdk.Tags.of(stack).add("Lab", lab)
    cdk.Tags.of(stack).add("Owner", OWNER)
    cdk.Tags.of(stack).add("TearDown", str(tear_down))

    app.synth()


if __name__ == "__main__":
    main()
