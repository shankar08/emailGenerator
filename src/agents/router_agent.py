from langsmith import traceable


class RouterAgent:
    @staticmethod
    def run(state):
        review = state.get("review", {})
        retry_count = state.get("retry_count", 0)
        max_retries = 3
        if not review:
            return {"route": "done"}
        if review.get("ok", True):
            return {"route": "done"}
        if retry_count >= max_retries:
            return {
                "route": "done",
                "reason": "max_retries_exceeded",
                "issues": review.get("issues", []),
                "retry_count": retry_count,
            }
        return {
            "route": "rewrite",
            "issues": review.get("issues", []),
            "retry_count": retry_count + 1,
        }
