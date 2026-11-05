import sys
from assistant.core.model import ModelInterface
from assistant.core.conversation import ConversationManager

import os
from assistant.repo.scanner import ProjectScanner
from assistant.repo.search import SearchEngine
from assistant.repo.parser import CodeParser
from assistant.repo.context import ContextBuilder 


scanner = ProjectScanner()
search_engine = SearchEngine(scanner)
parser = CodeParser()
context_builder = ContextBuilder(scanner=scanner) 


def print_help():
    print("\n--- Available Commands ---")
    print("/project        - Show project metadata & languages")
    print("/tree           - Display project folder structure")
    print("/files          - List all indexed source files")
    print("/search <query> - Search repository code")
    print("/symbols <file> - List symbols (classes/functions) in a file")
    print("/context <query>- Preview context retrieved for a question")
    print("/clear          - Clear conversation history")
    print("/help           - Show this message")
    print("/exit           - Quit the assistant")
    print("--------------------------\n")



def cmd_project(scanner):
    info = scanner.project_info
    files = scanner.get_all_files()
    languages = {scanner.get_file_metadata(f)["language"] for f in files}
    print(f"\n Project:   {info['project_name']}")
    print(f" Root:      {info['root_path']}")
    print(f" Git Repo:  {'Yes' if info['is_git_repo'] else 'No'}")
    print(f" Files:     {len(files)}")
    print(f" Languages: {', '.join(sorted(languages))}\n")

def cmd_tree(scanner):
    root = scanner.root_dir
    print(f"\n {os.path.basename(root)}/")
    valid_files = set(os.path.abspath(f) for f in scanner.get_all_files())
    
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter ignored directories
        dirnames[:] = [d for d in dirnames if not scanner.file_filter.should_ignore(os.path.join(dirpath, d))]
        level = os.path.relpath(dirpath, root).count(os.sep)
        if dirpath != root:
            indent = "   " * level
            print(f"{indent} {os.path.basename(dirpath)}/")
        sub_indent = "   " * (level + 1)
        for f in filenames:
            full_path = os.path.abspath(os.path.join(dirpath, f))
            if full_path in valid_files:
                print(f"{sub_indent} {f}")
    print()



def main():
    print("╭──────────────────────────────────────╮")
    print("│      Offline Coding Assistant        │")
    print("│         Powered by Cydags            │")
    print("╰──────────────────────────────────────╯")   
    
    # Initialize the components
    model = ModelInterface()
    conversation = ConversationManager()
    
    print("\nType /help for commands. Type /exit to quit.")

    while True:
        try:
            # Get user input
            user_input = input("\nYou > ").strip()
            
            # Handle empty input
            if not user_input:
                continue
                
            # Handle commands
            cmd_lower = user_input.lower()
            if cmd_lower == "/exit":
                print("Goodbye!")
                break
            elif cmd_lower == "/help":
                print_help()
                continue
            elif cmd_lower == "/clear":
                conversation.clear()
                print("[Conversation history cleared]")
                continue
            elif cmd_lower == "/project":
                cmd_project(scanner)
                continue
            elif cmd_lower == "/tree":
                cmd_tree(scanner)
                continue
            elif cmd_lower == "/files":
                print(f"\nIndexed Files ({len(scanner.get_all_files())}):")
                for f in scanner.get_all_files():
                    print(f"  • {os.path.relpath(f, scanner.root_dir)}")
                print()
                continue
            elif cmd_lower.startswith("/search "):
                query = user_input[8:].strip()
                hits = search_engine.search(query)
                print(f"\nFound {len(hits)} matches for '{query}':")
                for h in hits[:10]:
                    rel = os.path.relpath(h['file'], scanner.root_dir)
                    print(f"  {rel}:{h['line_num']}  {h['content']}")
                print()
                continue
            elif cmd_lower.startswith("/symbols "):
                target_file = user_input[9:].strip()
                syms = parser.parse_file(target_file)
                print(f"\nDiscovered {len(syms)} symbols in {target_file}:")
                for s in syms:
                    print(f"  • [{s.kind.upper():<6}] L{s.start_line}-{s.end_line}: {s.name}")
                print()
                continue
            elif cmd_lower.startswith("/context "):
                query = user_input[9:].strip()
                ctx = context_builder.build_context(query)
                print(f"\n{ctx or 'No relevant context found.'}\n")
                continue
                
            # Add user message to history
                        # 1. Build repo context for the user query
            repo_context = context_builder.build_context(user_input)
            
            # 2. Add single message to history (augmented if repo context exists)
            if repo_context:
                augmented_prompt = f"{repo_context}\nUser Question: {user_input}"
                conversation.add_user_message(augmented_prompt)
            else:
                conversation.add_user_message(user_input)

            # 3. Now fetch the updated conversation history
            messages = conversation.get_messages()

            print("\nCydags > ", end="", flush=True)

            # 4. Stream the model's response
            full_response = ""
            for token in model.generate_stream(messages):
                print(token, end="", flush=True)
                full_response += token

            print()

            # 5. Save assistant response to conversation history
            conversation.add_assistant_message(full_response)
            
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            print("\n[Operation cancelled by user]")
            continue
        except Exception as e:
            print(f"\n[An error occurred]: {e}")

if __name__ == "__main__":
    main()
