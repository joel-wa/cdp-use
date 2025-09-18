import requests
import json

class PromptLink:
    def __init__(self):
        self.prompt_links = {
            "Planner": "https://v0-prompt-version-control.vercel.app/api/prompts/1e572e0d-c523-4e58-8313-391e81af1950/production",
            "Critic":"https://v0-prompt-version-control.vercel.app/api/prompts/f0809117-56a7-458e-8a75-fe09eeab95b6/production",
            "Reviewer":"https://v0-prompt-version-control.vercel.app/api/prompts/9807c08c-ff44-4eaf-ae26-51c479e2c4ba/production"
            }

    def get_prompt(self, prompt_name):
        """
        Returns the prompt from the url of the prompt name
        
        Args:
            prompt_name (str): The name of the prompt to extract.
            
        Returns:
            str: The prompt content if found, otherwise None.
        """
        url = self.prompt_links.get(prompt_name, None)
        if url:
            response = requests.get(url)
            if response.status_code == 200:
                return json.loads(response.text).get("content", "")
        return None



if __name__ == "__main__":
    # Example usage
    prompt_link = PromptLink()
    prompt_name = "Planner"
    prompt = prompt_link.get_prompt(prompt_name)
    if prompt:
        print(f"Prompt for {prompt_name}:\n{prompt}")
    else:
        print(f"No prompt found for {prompt_name}.")