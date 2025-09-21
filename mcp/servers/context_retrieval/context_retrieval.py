import os
import chromadb
from chromadb.utils import embedding_functions
import pandas as pd

from mcp.server.fastmcp import FastMCP

from dotenv import load_dotenv
load_dotenv()

mcp = FastMCP("context_retrieval_server")
DEFAULT_WORKSPACE = os.getenv("CONTEXT_FOLDER")
zephyr_file_path = r"C:\Users\vidso\OneDrive - EG A S\Documents\AIHackathon\NeuronBackend\mcp\servers\context_retrieval\amazon_in_test_cases.xlsx"
embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    
@mcp.tool("get_test_script")
async def get_test_script(file_path:str=zephyr_file_path) -> str:
    """
    Extracts test script

    Args:
        file_path (str): Path to the Excel file containing the test scripts. Defaults to the Zephyr file path.

    Returns:
    """
    try:
        df = pd.read_excel(file_path)
        testscript_values = df['Test Script (Step-by-Step) - Step'].dropna()
        result_string = '/n'.join(testscript_values.astype(str))
        
        return result_string
    
    except Exception as e:
        return f"Error: {str(e)}"
    
@mcp.tool("query_knowledge_base")
async def query_knowledge_base(query:str,collection_name,db_path:str='./QaAgentackend/vectordb') -> str:
    """
    Queries a ChromaDB knowledge base collection using the provided query string.
    Loads the specified collection from the database path, performs a semantic search
    for the query, and returns the top matching documents as a single string separated
    by '/n/n'. Raises a ValueError if the database path or collection is invalid.

    Args:
        query (str): The search query string.
        collection_name: The name of the ChromaDB collection to query.
        db_path (str): Path to the ChromaDB database directory. Defaults to the project's vectordb folder.

    Returns:
        str: Concatenated string of the top matching documents, separated by '/n/n'. Raises ValueError on failure.
    """
    print(f"Loading collection '{collection_name}' from {db_path}...")    
    
    # Check if the db path exists
    if not os.path.exists(db_path):
        raise ValueError(f"Database directory '{db_path}' does not exist")
    
    # Initialize ChromaDB client with persistent storage
    client = chromadb.PersistentClient(path=db_path)
    
    try:
        # Get the existing collection
        collection = client.get_collection(
            name=collection_name,
            embedding_function=embedding_function
        )
        
        query_results = collection.query(
                    query_texts=[query],
                    n_results=2
                )
    
        return "/n/n".join(sum(query_results["documents"], []))
        
    except Exception as e:
        raise ValueError(f"Failed to query knowledge base '{collection_name}': {str(e)}")
    
if __name__ == "__main__":
    mcp.run(transport="stdio")