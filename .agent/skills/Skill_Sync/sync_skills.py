import os
import re

SKILLS_DIR = os.path.join(".agent", "skills")
AGENTS_FILE = os.path.join(".agent", "agents.md")

def extract_skill_info(skill_path):
    with open(skill_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract frontmatter or first header
    name_match = re.search(r'name:\s*"?(.*?)"?\n', content)
    desc_match = re.search(r'description:\s*"?(.*?)"?\n', content)
    trigger_match = re.search(r'trigger:\s*"?(.*?)"?\n', content)
    
    name = name_match.group(1) if name_match else os.path.basename(os.path.dirname(skill_path))
    desc = desc_match.group(1) if desc_match else "No description provided."
    trigger = trigger_match.group(1) if trigger_match else "N/A"
    
    return name, desc, trigger, skill_path

def sync():
    skills = []
    for root, dirs, files in os.walk(SKILLS_DIR):
        if "SKILL.md" in files:
            skills.append(extract_skill_info(os.path.join(root, "SKILL.md")))
    
    if not os.path.exists(AGENTS_FILE):
        print(f"Error: {AGENTS_FILE} not found.")
        return

    with open(AGENTS_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find the skills index table section
    start_idx = -1
    end_idx = -1
    for i, line in enumerate(lines):
        if "## 5. Available Skills Index" in line:
            start_idx = i + 2 # Header + Table Header row
            break
    
    if start_idx != -1:
        # Simple table reconstruction
        new_table = ["| Skill Name | Trigger | Descripción |\n", "| :--- | :--- | :--- |\n"]
        for name, desc, trigger, path in sorted(skills):
            rel_path = path.replace("\\", "/") # Normalize for markdown links
            new_table.append(f"| **[{name}](file:///{os.path.abspath(path).replace('\\', '/')})** | `{trigger}` | {desc} |\n")
        
        # Replace the old table (assuming it ends at a horizontal rule or end of file)
        for i in range(start_idx, len(lines)):
            if lines[i].strip() == "---" or i == len(lines) - 1:
                end_idx = i
                break
        
        if end_idx != -1:
            # We keep everything up to the section title, then our new table, then the rest
            new_content = lines[:start_idx-2] # Keep title
            new_content.append("## 5. Available Skills Index\n\n")
            new_content.extend(new_table)
            new_content.append("\n---\n")
            new_content.extend(lines[end_idx+1:])
            
            with open(AGENTS_FILE, 'w', encoding='utf-8') as f:
                f.writelines(new_content)
            print("Successfully synced skills to agents.md")

if __name__ == "__main__":
    sync()
