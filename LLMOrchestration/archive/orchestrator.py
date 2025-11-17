from typing import Callable, Dict, Any, List

RoleFn = Callable[[Dict[str, Any]], Dict[str, Any]]

class AdvancedOrchestrator:
    """
    Advanced Orchestrator orchestrator:
    - Runs each role in the given order once per run.
    - Each role sees everything produced so far.
    - Returns all outputs + a 'final' key (last role's output).
    - Supports run_until_stop to repeat the sequence until a stop_sequence is found in any output.
    """
    def __init__(self, roles: Dict[str, RoleFn], order: List[str], stop_sequence: str = None):
        self.roles = roles
        self.order = order
        self.stop_sequence = stop_sequence

    def run(self, task: str) -> Dict[str, Any]:
        context: Dict[str, Any] = {"input": task}
        for role in self.order:
            fn = self.roles[role]
            output = fn(context)
            context[role] = output
        context["final"] = context[self.order[-1]]
        return context

    def run_until_stop(self, task: str) -> Dict[str, Any]:
        """Run the full role sequence repeatedly until stop_sequence is found in any output."""
        if not self.stop_sequence:
            raise ValueError("No stop_sequence defined for orchestrator.")
        context: Dict[str, Any] = {"input": task}
        while True:
            for role in self.order:
                fn = self.roles[role]
                output = fn(context)
                context[role] = output
                # Check if stop_sequence is in the output (as a string or dict value)
                if self._contains_stop_sequence(output):
                    context["final"] = context[self.order[-1]]
                    return context
            # If no stop after full cycle, continue (context accumulates)

    def _contains_stop_sequence(self, output: Any) -> bool:
        """Helper to check if stop_sequence is in the output (handles dicts/strings)."""
        if isinstance(output, dict):
            return any(self.stop_sequence in str(v) for v in output.values())
        return self.stop_sequence in str(output)

def planner(ctx):
    goal = ctx["input"]
    summary = ""
    notes = ""
    if "reviewer" in ctx:
        summary = ctx["reviewer"]["summary"]
        notes = ctx["reviewer"]["notes"]
    return {"plan": f"Plan created for: {goal} {summary} {notes}"}

def executor(ctx):
    plan = ctx["planner"]["plan"]
    return {"result": f"Executed -> {plan}"}

def critic(ctx):
    plan = ctx["planner"]["plan"]
    return {"critique": f"Reviewing {plan}."}

def reviewer(ctx):
    return {
        "summary": ctx["executor"]["result"],
        "notes": ctx["critic"]["critique"]
    }

roles = {
    "planner": planner,
    "executor": executor,
    "critic": critic,
    "reviewer": reviewer,
}

order = ["planner", "critic", "executor", "reviewer"]

orchestrator = AdvancedOrchestrator(roles, order, stop_sequence="goal_achieved")

# Example: Single run
out = orchestrator.run("Expand a bakery business")

print(out["final"])   # reviewer output

# Example: Run until stop (assuming reviewer outputs something with "goal_achieved")
# Modify reviewer to include stop_sequence for testing
def reviewer(ctx):
    value = input("Input review: ")
    return {
        "summary": ctx["executor"]["result"] + value,
        "notes": ctx["critic"]["critique"]
    }

orchestrator.roles["reviewer"] = reviewer
out_stop = orchestrator.run_until_stop("Expand a bakery business")
print(out_stop["final"])
