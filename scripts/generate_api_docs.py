import os
import re
import pathlib

def extract_docstring(file_path):
    """Extracts docstrings from a Python or PowerShell file."""
    if file_path.endswith(".py"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Use regex to find docstrings
                docstring_match = re.search(r'"""([\s\S]*?)"""', content)
                if docstring_match:
                    return docstring_match.group(1).strip()
                else:
                    return None
        except Exception as e:
            return f"Error reading {file_path}: {e}"

    elif file_path.endswith(".ps1"):
        try:
            # For PS1, we look for <# ... #> blocks at the top
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                docstring_match = re.search(r'<#([\s\S]*?)#>', content)
                if docstring_match:
                    return docstring_match.group(1).strip()
                else:
                    return None
        except Exception as e:
            return f"Error reading {file_path}: {e}"
    else:
        return "Unsupported file type."


def generate_api_reference(directory="scripts"):
    """Generates a Markdown file with API documentation."""
    api_reference = "# API Reference\n\n"
    scripts_path = pathlib.Path(directory)
    if not scripts_path.exists():
        return f"Error: {directory} not found."
        
    scripts = sorted([f.name for f in scripts_path.glob("*") if f.suffix in (".py", ".ps1")])
    
    for filename in scripts:
        file_path = os.path.join(directory, filename)
        api_reference += f"## {filename}\n\n"
        docstring = extract_docstring(file_path)
        if docstring:
            # Clean up indentation in docstring
            lines = docstring.split('\n')
            clean_lines = [l.strip() for l in lines]
            api_reference += "\n".join(clean_lines) + "\n\n"
        else:
            api_reference += "*No documentation provided.*\n\n"

    return api_reference


def write_api_reference(api_reference, output_file="docs/API_REFERENCE.md"):
    """Writes the API reference to a Markdown file."""
    output_path = pathlib.Path(output_file)
    if not output_path.parent.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
         output_path.write_text(api_reference, encoding="utf-8")
    except Exception as e:
        print(f"Error writing to {output_file}: {e}")


if __name__ == "__main__":
    scripts_dir = "scripts"
    api_docs = generate_api_reference(scripts_dir)
    write_api_reference(api_docs)
    print("API documentation generated in docs/API_REFERENCE.md")
