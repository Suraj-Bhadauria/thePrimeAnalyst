HOW TO RUN THIS ? 

1. clone it 
2. make venv using : python -m venv venv
3. activate venv   : venv\scripts\activate
4. install dependencies: pip install -r requirement.txt
5. create an .env in root folder and paste the below content in it (pls generate and use ur own groq key)
    GROQ_API_KEY=afafafafa
    MODEL_NAME=llama-3.3-70b-versatile
    TEMPERATURE=0.1



RUN 
1. IF YOU WANT TO TEST IT 
- run "py test_workflow.py"

2. IF YOU WANT TO SEE THE STREAMLIT UI APP
- run "streamlit run app.py"