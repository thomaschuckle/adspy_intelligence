import boto3
import os

lambda_client = boto3.client("lambda")

def lambda_handler(event=None, context=None):
    """
    Kill or restore concurrency for Lambda functions.

    Environment Variables:
      - DEFAULT_FUNCTIONS: comma-separated list of function names (optional)
      - DEFAULT_ACTION: 'kill' or 'restore' (default: 'kill')
      - DEFAULT_RESTORE_VALUE: integer, used if RESTORE_MODE='fixed' (default: 5)
      - RESTORE_MODE: 'delete' (remove limit) or 'fixed' (restore to DEFAULT_RESTORE_VALUE)
    """

    # --- Default values from environment variables ---
    default_functions = os.environ.get("DEFAULT_FUNCTIONS", "")
    default_action = os.environ.get("DEFAULT_ACTION", "kill")
    default_restore_value = int(os.environ.get("DEFAULT_RESTORE_VALUE", "5"))
    restore_mode = os.environ.get("RESTORE_MODE", "delete").lower()  # 'delete' or 'fixed'

    # --- Read from event or fallback to defaults ---
    functions = event.get("functions") if event and "functions" in event else []
    if not functions and default_functions:
        functions = [f.strip() for f in default_functions.split(",") if f.strip()]

    action = event.get("action") if event and "action" in event else default_action
    restore_value = event.get("restore_value") if event and "restore_value" in event else default_restore_value

    if not functions:
        return {"error": "No functions specified."}

    results = []

    for fn in functions:
        try:
            if action == "kill":
                lambda_client.put_function_concurrency(
                    FunctionName=fn,
                    ReservedConcurrentExecutions=0
                )
                results.append({"function": fn, "status": "killed"})
            elif action == "restore":
                if restore_mode == "delete":
                    lambda_client.delete_function_concurrency(FunctionName=fn)
                    results.append({"function": fn, "status": "restored (unlimited)"})
                elif restore_mode == "fixed":
                    lambda_client.put_function_concurrency(
                        FunctionName=fn,
                        ReservedConcurrentExecutions=int(restore_value)
                    )
                    results.append({"function": fn, "status": f"restored (fixed={restore_value})"})
                else:
                    results.append({"function": fn, "status": f"invalid restore_mode '{restore_mode}'"})
            else:
                results.append({"function": fn, "status": f"invalid action '{action}'"})
        except Exception as e:
            results.append({"function": fn, "error": str(e)})

    return {
        "action": action,
        "restore_mode": restore_mode,
        "results": results
    }
