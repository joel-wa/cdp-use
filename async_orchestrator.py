from typing import Callable, Dict, Any, List, Awaitable, Union
import asyncio

AsyncRoleFn = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]

class AsyncAdvancedOrchestrator:
    """
    Async Advanced Orchestrator:
    - Runs each role in the given order once per run.
    - Each role sees everything produced so far.
    - Returns all outputs + a 'final' key (last role's output).
    - Supports run_until_stop to repeat the sequence until a stop_sequence is found in any output.
    """
    def __init__(self, roles: Dict[str, AsyncRoleFn], order: List[str], stop_sequence: str = None):
        self.roles = roles
        self.order = order
        self.stop_sequence = stop_sequence

    async def run(self, task: str) -> Dict[str, Any]:
        """Run the role sequence once"""
        context: Dict[str, Any] = {"input": task}
        for role in self.order:
            fn = self.roles[role]
            output = await fn(context)
            context[role] = output
        context["final"] = context[self.order[-1]]
        return context

    async def run_until_stop(self, task: str) -> Dict[str, Any]:
        """Run the full role sequence repeatedly until stop_sequence is found in any output."""
        if not self.stop_sequence:
            raise ValueError("No stop_sequence defined for orchestrator.")
        context: Dict[str, Any] = {"input": task}
        iteration = 0
        max_iterations = 10  # Safety limit
        
        while iteration < max_iterations:
            iteration += 1
            print(f"\n🔄 Orchestrator iteration {iteration}")
            
            for role in self.order:
                print(f"  ▶️ Executing role: {role}")
                fn = self.roles[role]
                output = await fn(context)
                context[role] = output
                
                # Check if stop_sequence is in the output (as a string or dict value)
                if self._contains_stop_sequence(output):
                    print(f"  ✅ Stop sequence '{self.stop_sequence}' found in {role} output")
                    context["final"] = context[self.order[-1]]
                    context["iterations"] = iteration
                    return context
            
            print(f"  🔄 Iteration {iteration} complete, continuing...")
            
        print(f"⚠️ Maximum iterations ({max_iterations}) reached")
        context["final"] = context[self.order[-1]]
        context["iterations"] = iteration
        return context

    def _contains_stop_sequence(self, output: Any) -> bool:
        """Helper to check if stop_sequence is in the output (handles dicts/strings)."""
        if isinstance(output, dict):
            return any(self.stop_sequence in str(v) for v in output.values())
        return self.stop_sequence in str(output)
