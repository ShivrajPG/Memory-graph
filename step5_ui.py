import streamlit as st
import os
import json
import streamlit.components.v1 as components

from dotenv import load_dotenv
from neo4j import GraphDatabase
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from pyvis.network import Network

load_dotenv()
URI = os.getenv("NEO4J_URI")
Username = os.getenv("NEO4J_USERNAME")
Password = os.getenv("NEO4J_PASSWORD")
GROQ_Key= os.getenv("GROQ_API_KEY")

@st.cache_resource
def get_driver():
    return GraphDatabase.driver(URI, auth=(Username, Password))

driver = get_driver()
llm = ChatGroq(temperature=0, model_name="llama-3.3-70b-versatile", groq_api_key=GROQ_Key)

class QueryPlan(BaseModel):
    search_terms: list[str] = Field(description="Extract the core keywords from the user's question.")
structured_llm = llm.with_structured_output(QueryPlan)

def retrieve_context_pack(question: str):
    plan = structured_llm.invoke(f"Extract keywords from this question: '{question}'")
    raw_terms =[t.lower() for t in plan.search_terms]
    
    mapped_terms =[]
    for t in raw_terms:
        if "bug" in t: mapped_terms.extend(["issue", "reported"])
        elif "fix" in t or "solve" in t: mapped_terms.append("resolved")
        elif "person" in t or "who" in t: mapped_terms.append("user")
        else: mapped_terms.append(t)
        
    search_terms = list(set(raw_terms + mapped_terms))
    if not search_terms: return [],[]

    context_pack =[]
    with driver.session() as session:
        query = """
        MATCH (n:Entity)-[r]->(m:Entity)
        WHERE any(term IN $terms WHERE 
            toLower(n.name) CONTAINS term OR 
            toLower(n.type) CONTAINS term OR 
            toLower(type(r)) CONTAINS term OR 
            toLower(m.name) CONTAINS term)
        RETURN n.name AS subject, n.type AS sub_type, type(r) AS relation, m.name AS object, m.type AS obj_type, r.evidence AS evidence
        LIMIT 15
        """
        result = session.run(query, terms=search_terms)
        for record in result:
            if record.data() not in context_pack:
                context_pack.append(record.data())
                
    return search_terms, context_pack

def synthesize_answer(question: str, context_pack: list):
    context_string = ""
    for i, item in enumerate(context_pack):
        evidence_list = json.loads(item['evidence'])
        quotes = " | ".join([ev['excerpt'] for ev in evidence_list])
        context_string += f"[Citation {i+1}]: {item['subject']} {item['relation']} {item['object']}. Proof: '{quotes}'\n"
    
    prompt = f"""You are the Layer10 AI Memory Agent. 
    Answer the user's question using ONLY the Grounded Context below. 
    CRITICAL RULES:
    1. Keep your answer EXTREMELY BRIEF and CONCISE (Maximum 2 sentences).
    2. You MUST cite the [Citation Number] inline.
    
    Context:
    {context_string}
    
    Question: {question}
    Answer:"""
    return llm.invoke(prompt).content

st.set_page_config(page_title="Layer10 Memory System", layout="wide")
st.title("Layer10 Grounded RAG Agent")

tab1, tab2 = st.tabs(["Chat Interface", "Interactive Visual Graph"])

with tab1:

    st.markdown("Chat with the organizational memory graph. Citations are verified and grounded.")
    
    if "messages" not in st.session_state:
        st.session_state.messages =[]

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if question := st.chat_input("Ask the Memory Graph..."):
       
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Querying Neo4j Graph..."):
                terms, context_pack = retrieve_context_pack(question)
                
                if not context_pack:
                    st.error("No grounded evidence found in the long-term memory for this question.")
                    st.session_state.messages.append({"role": "assistant", "content": "No grounded evidence found."})
                else:
                    final_answer = synthesize_answer(question, context_pack)
                    st.markdown(final_answer)
                    
                    st.caption(f"*Backend Diagnostics: Mapped Terms {terms} | Found {len(context_pack)} connections.*")
                    
                    for i, item in enumerate(context_pack):
                        with st.expander(f"[Citation {i+1}]: {item['subject']} ➡️ {item['relation']} ➡️ {item['object']}"):
                            evidence_list = json.loads(item['evidence'])
                            for ev in evidence_list:
                                st.success(f"\"{ev['excerpt']}\"")
                                st.markdown(f"[GitHub Source]({ev['url']})")
                    
                    st.session_state.messages.append({"role": "assistant", "content": final_answer})

with tab2:

    st.subheader("Interactive Knowledge Graph")
    
    with driver.session() as session:
        query = "MATCH (n)-[r]->(m) RETURN n.name AS source, type(r) AS relation, m.name AS target, n.type AS source_type, m.type AS target_type"
        graph_data =[r.data() for r in session.run(query)]
        
    if graph_data:
        net = Network(height="600px", width="100%", bgcolor="#0E1117", font_color="white", directed=True, filter_menu=True, cdn_resources='remote')
        
        for record in graph_data:
            color_map = {"USER": "#4CAF50", "ISSUE": "#F44336", "COMPONENT": "#2196F3", "CONCEPT": "#FFEB3B"}
            src_color = color_map.get(record["source_type"], "#9E9E9E")
            tgt_color = color_map.get(record["target_type"], "#9E9E9E")
            
            net.add_node(record["source"], label=record["source"], color=src_color)
            net.add_node(record["target"], label=record["target"], color=tgt_color)
            net.add_edge(record["source"], record["target"], title=record["relation"], label=record["relation"])
            
        net.show_buttons(filter_=['physics'])
        net.save_graph("neo4j_graph.html")
        
        HtmlFile = open("neo4j_graph.html", 'r', encoding='utf-8')
        components.html(HtmlFile.read(), height=800)

