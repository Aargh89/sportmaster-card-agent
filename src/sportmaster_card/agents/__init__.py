"""CrewAI agents for the Sportmaster Card Agent system.

Each agent has a specialized role in the product card pipeline.
Agents are organized by contour (UC1–UC4).

Agent naming convention:
    - Module name: snake_case (e.g., data_validator.py)
    - Class name: PascalCase + 'Agent' suffix (e.g., DataValidatorAgent)
    - Agent ID: dot-separated (e.g., 'uc1.data_validator')
"""
