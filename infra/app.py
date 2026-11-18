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
from stacks.lab04_lakehouse import Lab04Lakehouse
from stacks.lab04_member import Lab04Member

PROJECT = "sap-c03-labs"
OWNER = os.environ.get("SAP_LABS_OWNER", "steven")
DEFAULT_REGION = os.environ.get("CDK_DEFAULT_REGION", "us-east-1")

# Registered labs. Add the import and the entry together.
STACKS: dict[str, type[cdk.Stack]] = {
    "02": Lab02MultitenantApi,
    "04": Lab04Lakehouse,
}
# Auxiliary stacks deployed to the second account with `-c member=1`.
MEMBER_STACKS: dict[str, type[cdk.Stack]] = {
    "04": Lab04Member,
}


def main() -> None:
    app = cdk.App()

    lab = str(app.node.try_get_context("lab") or "02")
    member = bool(app.node.try_get_context("member"))
    registry = MEMBER_STACKS if member else STACKS
    if lab not in registry:
        available = ", ".join(sorted(registry))
        kind = "member stack" if member else "stack"
        print(
            f"lab={lab!r} has no {kind} yet. Registered: {available}. "
            f"Write infra/stacks/lab{lab}_*.py and register it in infra/app.py.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    tear_down = app.node.try_get_context("tearDown") or str(
        date.today() + timedelta(days=1)
    )

    stack_id = f"SapC03Lab{lab}Member" if member else f"SapC03Lab{lab}"
    stack = registry[lab](
        app,
        stack_id,
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

    if app.node.try_get_context("nag"):
        from cdk_nag import AwsSolutionsChecks

        cdk.Validations.of(app).add_plugins(AwsSolutionsChecks(app, verbose=True))

    app.synth()


if __name__ == "__main__":
    main()
