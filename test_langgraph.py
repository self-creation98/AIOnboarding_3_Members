import sys
import json

# Setup encoding for Windows/terminals to prevent print errors
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

# Import the LangGraph workflow directly
from src.backend.rag.graph import chatbot_graph

def test_graph(user_message: str):
    print(f"\n{'='*50}")
    print(f"USER MESSAGE: {user_message}")
    print(f"{'='*50}")
    
    # 1. Define the initial state (Mocking what the FastAPI route normally provides)
    initial_state = {
        "employee_id": "mock-emp-123",
        "original_message": user_message,
        "employee_context": {
            "id": "mock-emp-123",
            "full_name": "Test User",
            "role": "nhan_vien_moi",
            "department": "IT"
        },
        "actions_taken": [],
        "relevant_documents": [],
        "sources": [],
        "final_answer": ""
    }

    print("Executing Graph...\n")
    
    # 2. Invoke the graph 
    final_state = chatbot_graph.invoke(initial_state)
    
    # 3. Print the results
    print("\n--- GRAPH EXECUTION COMPLETE ---")
    print(f"Final Intent: {final_state.get('intent')}")
    print(f"Final Answer: {final_state.get('final_answer')}")
    print(f"Sources:      {final_state.get('sources')}")
    print(f"Actions:      {final_state.get('actions_taken')}")
    
    # Optional: print the entire state for debugging
    # print("\nFull State Output:")
    # print(json.dumps(final_state, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_graph("Chính sách nghỉ phép của công ty là gì?")
