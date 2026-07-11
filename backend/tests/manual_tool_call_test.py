from services.ollama_client import OllamaClient
from services.tool_registry import get_tool_schemas


def main():
    client = OllamaClient(model="qwen3:4b")

    response = client.chat_with_tools(
        messages=[
            {
                "role": "system",
                "content": (
                    "Use the provided tool when the user asks "
                    "you to inspect workspace files."
                ),
            },
            {
                "role": "user",
                "content": (
                    "List the files at the workspace root."
                ),
            },
        ],
        tools=get_tool_schemas(
            ["list_files", "read_file"]
        ),
        options={
            "temperature": 0.1,
            "num_predict": 512,
        },
    )

    print(response)


if __name__ == "__main__":
    main()