# To run this code you need to install the following dependencies:
# pip install google-genai

import base64
import os
from google import genai
from google.genai import types
from prompt_link import PromptLink
import json



class OrchestratorLLM:
    def __init__(self, api_key=None, model="gemini-2.5-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY","AIzaSyCPvAs10rueqcU71T7B7SpckJZVQKVwa5w")
        self.model = model
        self.router_model = "gemini-2.5-flash-lite"
        self.client = genai.Client(api_key=self.api_key)

    def generate_plan(self, user_goal):
        """
        Generate a strategic plan with executor routing based on user goal.
        Returns a plan with specific action and executor route (browser/syntron/table).
        """
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=user_goal),
                ],
            ),
        ]
        
        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_budget=0,
            ),
            system_instruction=[
                types.Part.from_text(text=PromptLink().get_prompt("Planner")),
            ],
            response_mime_type="application/json",
            response_schema= types.Schema(
            type = types.Type.OBJECT,
            required = ["Action", "route"],
            properties = {
                "Action": types.Schema(
                    type = types.Type.STRING,
                ),
                "route": types.Schema(
                    type = types.Type.STRING,
                ),
            },
        ),
        )

        response_text = ""
        for chunk in self.client.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=generate_content_config,
        ):
            response_text += chunk.text
        
        return response_text.strip()


if __name__ == "__main__":
    # Example usage as a function
    def generate(user_input, function_declarations=None):
        llm = OrchestratorLLM()
        return llm.generate_plan(user_input)



    goal = """
    Optimize Joel's X profile (bio, profile picture, banner) to clearly reflect 'AI influencer' niche and expertise, incorporating relevant keywords.
    """
    # print(generate("Grow the user's Twitter following by 100 followers in the AI niche"))
    result = generate("Optimize Joel's X profile (bio, profile picture, banner) to clearly reflect 'AI influencer' niche and expertise, incorporating relevant keywords.")
    print(result)
