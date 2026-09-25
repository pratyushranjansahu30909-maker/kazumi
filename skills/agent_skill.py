import re
from .base_skill import KazumiSkill

class AgentSkill(KazumiSkill):
    def get_triggers(self):
        return [
            r"^/agent",
            r"\b(and then|after that|first.*then|do both|lock.*and|open.*and|volume.*and)\b"
        ]

    def get_help(self):
        return "/agent <complex instruction>", "Runs a multi-step execution loop to coordinate multiple actions."

    def handle(self, text, clean_text, valence):
        query = text
        if clean_text.startswith("/agent"):
            parts = text.split(" ", 1)
            if len(parts) > 1:
                query = parts[1].strip()
            else:
                return "(Kazumi stands ready...) Tell me what complex steps you'd like me to perform! 🌸"

        # Build tools registry from dynamic skill manager
        tools = {}
        for skill in self.bot.skill_manager.skills:
            if skill == self:
                continue
            name = skill.__class__.__name__.replace("Skill", "").lower()
            tools[name] = skill

        # Max agent loop iterations
        max_iterations = 3
        
        # Build description of tools
        tools_desc = "\n".join([f"- {name}: triggered by setting Action: {name}. Handles commands matching: {', '.join(skill.get_triggers())}" for name, skill in tools.items()])
        
        system_instructions = f"""You are Kazumi, an empathetic feminine companion and system agent. You can perform multi-step tasks by calling tools.
Available tools:
{tools_desc}

To use a tool, you MUST use the following format:
Thought: [Reason about what to do next]
Action: [tool_name]
Action Input: [argument or command trigger query for the tool]

After your Action block, the system will execute it and provide the result:
Observation: [Tool result]

Repeat this loop as needed. Once you have completed all tasks, respond using this format:
Thought: I have completed the tasks
Final Answer: [Your warm, cozy final response to the user summarizing what was done]

Begin!
User Query: {query}
"""

        current_prompt = system_instructions
        for iteration in range(max_iterations):
            try:
                # Retrieve LLM client from bot controller
                client = getattr(self.bot.controller, "client", None)
                from kazumi import API_KEY
                
                if client is None or not API_KEY or API_KEY in ("your_api_key_here", ""):
                    return "(Kazumi shrugs...) The AI engine is currently offline or lacks API credentials, so I can only perform single-step commands. 🌸"
                
                messages = [
                    {"role": "system", "content": "You are Kazumi, a helpful agentic companion."},
                    {"role": "user", "content": current_prompt}
                ]
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=250,
                    temperature=0.0
                )
                output = response.choices[0].message.content
                
                # Check for Final Answer
                if "Final Answer:" in output:
                    final_ans = output.split("Final Answer:", 1)[1].strip()
                    return final_ans
                
                # Parse Action and Action Input
                action_match = re.search(r"Action:\s*(\w+)", output)
                action_input_match = re.search(r"Action Input:\s*(.*)", output)
                
                if action_match and action_input_match:
                    tool_name = action_match.group(1).lower().strip()
                    tool_input = action_input_match.group(1).strip()
                    
                    if tool_name in tools:
                        tool_result = tools[tool_name].handle(tool_input, tool_input, 0.0)
                        observation = f"Observation: {tool_result}"
                    else:
                        observation = f"Observation: Error - Tool '{tool_name}' is not available."
                    
                    current_prompt += f"\n{output}\n{observation}"
                else:
                    return "(Kazumi looks confused...) I tried to process that, but the steps got a bit tangled. Let me just chat instead! 🌸"
            except Exception as e:
                return f"Agent execution failed: {e}"

        return "(Kazumi checks her list...) I hit the maximum steps limit while processing. Let's do something simpler next time! 🌸"
