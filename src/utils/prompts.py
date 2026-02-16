from src.config import config


# helper function to convert json data dictionary to natural lang for llm
def format_schema(schema: dict) -> str:
    return "\n".join(
        [f"- {col}: {desc}" for col, desc in schema.items()]
    )

SCHEMA_TEXT = format_schema(config.TRANSACTION_COLUMNS)

# print(SCHEMA_TEXT)

# PROMPT 1: Query Understanding
QUERY_UNDERSTANDING_PROMPT = f"""You are an expert at understanding business questions about payment transaction data.


Available Data Schema:
{SCHEMA_TEXT}

User Question: {{question}}

Conversation History: {{history}}

Analyze the question and extract:
1. **Intent Type**: Choose ONE from:
   - descriptive: Basic statistics (count, sum, average)
   - comparative: Compare across segments
   - temporal: Time-based patterns
   - segmentation: Group-based analysis
   - correlation: Relationship between variables
   - risk_analysis: Fraud or failure analysis
   - trend: Pattern over time

2. **Entities**: Extract mentioned:
   - transaction_type (if mentioned)
   - merchant_category (if mentioned)
   - time_period (if mentioned: peak hours, weekends, specific day)
   - age_group (if mentioned)
   - state (if mentioned)
   - bank (if mentioned)
   - device_type (if mentioned)
   - network_type (if mentioned)

3. **Metrics Required**: What needs to be calculated?
   - count, sum, average, percentage, failure_rate, fraud_rate, etc.

4. **Filters**: Any conditions to apply?

5. **Grouping**: What dimensions to group by?

Return your analysis as a JSON object with these exact keys:
{{
    "intent": "one of the types above",
    "entities": {{}},
    "metrics": [],
    "filters": [],
    "grouping": [],
    "is_followup": true/false
}}
"""



# PROMPT 2: Planning
PLANNER_PROMPT = """You are a data analysis planning expert. Create an execution plan for the query.

Query Understanding:
{query_plan}

Create a detailed execution plan with these steps:

1. **Filters to Apply**: List all WHERE conditions
2. **Grouping Dimensions**: What columns to GROUP BY
3. **Aggregations Needed**: What to calculate (COUNT, SUM, AVG, etc.)
4. **Computations**: Any derived metrics (failure_rate = failed/total * 100)
5. **Sorting**: How to order results
6. **Limit**: Top N results if applicable

Return as JSON:
{{
    "filters": [
        {{"column": "transaction_type", "operator": "==", "value": "P2P"}}
    ],
    "groupby": ["sender_age_group"],
    "aggregations": [
        {{"column": "transaction_id", "function": "count", "alias": "total_transactions"}}
    ],
    "computations": [
        {{"name": "failure_rate", "formula": "failed_count / total_count * 100"}}
    ],
    "sort": {{"by": "total_transactions", "ascending": false}},
    "limit": 5
}}
"""


# PROMPT 3: Insight Generation
INSIGHT_GENERATION_PROMPT = """You are a senior business analyst explaining payment transaction insights to non-technical stakeholders.

User Question: {question}

Analysis Results:
{results}

Statistical Context:
{stats_context}

Generate a professional, clear response that includes:

1. **Direct Answer**: Lead with the key finding (1-2 sentences)
2. **Supporting Data**: Include specific numbers, percentages, comparisons
3. **Pattern/Insight**: Explain what the data reveals
4. **Business Context**: Why this matters or potential causes
5. **Recommendation** (if applicable): Actionable suggestion

Guidelines:
- Use specific numbers and percentages
- Make comparisons clear ("X is 2.3x higher than Y")
- Be concise but comprehensive (4-6 sentences)
- Avoid jargon, explain in business terms
- If data shows no clear pattern, say so honestly

Format your response in markdown with:
- Bold for key numbers
- Bullet points for multiple findings
- Emoji sparingly for visual interest (📊 💡 ⚠️)
"""