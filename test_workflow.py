from src.graph.workflow import Workflow
from src.utils.data_loader import data_loader

# Load data
print("Loading data...")
data_loader.load_data()

# Initialize workflow
print("Initializing workflow...")
workflow = Workflow()

# Test questions
test_questions = [
    "What is the average transaction amount?",
    "Which age group uses P2P most?",
    "Compare failure rates between Android and iOS"
]

for question in test_questions:
    print(f"\n{'='*60}")
    print(f"Question: {question}")
    print(f"{'='*60}")
    
    response = workflow.run(question)
    
    print(f"\nResponse:")
    print(response)
    print(f"\n{'='*60}\n")