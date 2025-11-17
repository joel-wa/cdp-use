class LLMOrchestrator:

    def __init__(self, roles: dict, order: list, stop_sequence: str = None):
        """
        roles: dict mapping role names to functions
        order: list of role names defining execution order
        stop_sequence: string to stop the loop when found in output
        """
        self.roles = roles
        self.order = order
        self.index = 0
        self.stop_sequence = stop_sequence

    def next_role(self):
        """Switch to the next role and return it."""
        role = self.order[self.index]
        self.index = (self.index + 1) % len(self.order)  # cycle through
        return role

    def run(self, *args, **kwargs):
        """Run the current role function with given arguments."""
        role = self.next_role()
        fn = self.roles.get(role)
        if fn is None:
            raise ValueError(f"No function defined for role: {role}")
        return fn(*args, **kwargs)

    def run_until_stop(self, *args, **kwargs):
        """Run roles in order until stop_sequence is found in output."""
        if not self.stop_sequence:
            raise ValueError("No stop_sequence defined for orchestrator.")
        output = ""
        while self.stop_sequence not in output:
            output = self.run(*args, **kwargs)
            print(output)
        return output


# Example usage
def planner(task):
    return f"[Planner] Breaking down task: {task}"

def reviewer(task):
    return f"[Reviewer] Reviewing the Output for plan for task: {task} goal_achieved"

def executor(task):
    return f"[Executor] Executing task: {task}"


orchestrator = LLMOrchestrator(
    roles={
        "planner": planner,
        "executor": executor,
        "reviewer": reviewer
    },
    order=["planner", "executor", "reviewer"],
    stop_sequence="goal_achieved"
)

# Example: run until stop sequence is found
orchestrator.run_until_stop("Build a chatbot")
