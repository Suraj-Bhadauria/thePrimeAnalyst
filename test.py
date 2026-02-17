# ROUGH COMPONENT AND SNIPPET TESTING
# YOU CAN IGNORE IT

from src.agents.query_agent import QueryPlan, QueryUnderstandingAgent

obj = QueryUnderstandingAgent();

# question = "What is the total transaction amount?"
# question = "How many transactions were successful?"
# question = "How many P2P vs P2M transactions are there?"
question = "What is the total amount spent in Delhi?"

queryPlan = obj.understand_query({question})

print(queryPlan)
