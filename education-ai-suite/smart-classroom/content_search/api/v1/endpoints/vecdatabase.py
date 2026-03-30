import logging
from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any

from providers.chromadb_wrapper.chroma_client import ChromaClientWrapper

logger = logging.getLogger(__name__)

# Initialize the ChromaDB Wrapper
chroma_db = ChromaClientWrapper()

router = APIRouter()

# --- Data Query Endpoints ---

@router.get("/list-ids")
async def list_ids(collection_name: str):
    """
    Retrieve all document IDs present in a specific collection.
    """
    results = chroma_db.query_all(collection_name=collection_name)
    if not results:
        # Return empty list instead of 404 to avoid breaking frontend loops
        return {"ids": [], "count": 0}
    
    ids = [item['id'] for item in results]
    return {"ids": ids, "count": len(ids)}

@router.post("/get-by-ids")
async def get_by_ids(collection_name: str, ids: List[str], include_vector: bool = False):
    """
    Fetch specific records (metadata and optionally vectors) by their IDs.
    """
    output_fields = ['meta']
    if include_vector:
        output_fields.append('vector')
    
    try:
        results = chroma_db.get(ids=ids, output_fields=output_fields, collection_name=collection_name)
        return {"results": results}
    except Exception as e:
        logger.error(f"Error fetching IDs {ids}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during data retrieval")

@router.post("/search")
async def search_vectors(
    collection_name: str, 
    query_embeddings: List[List[float]], 
    n_results: int = 5,
    where: Optional[Dict[str, Any]] = None
):
    """
    Perform vector similarity search. 
    Main entry point for 'search by image' or 'search by text' features.
    """
    try:
        results = chroma_db.query(
            collection_name=collection_name,
            query_embeddings=query_embeddings,
            where=where,
            n_results=n_results
        )
        return {"results": results}
    except Exception as e:
        logger.error(f"Vector search failed in {collection_name}: {e}")
        raise HTTPException(status_code=500, detail="Vector search execution failed")

# --- Data Manipulation Endpoints ---

@router.post("/insert")
async def insert_data(collection_name: str, data: List[Dict[str, Any]]):
    """
    Insert new vector data and metadata into the collection.
    Expects data format: [{"id": "uuid", "vector": [...], "meta": {...}}]
    """
    try:
        res = chroma_db.insert(data=data, collection_name=collection_name)
        return {"status": "success", "info": res}
    except Exception as e:
        logger.error(f"Insertion failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid data format or database connection error")

@router.delete("/delete")
async def delete_data(collection_name: str, ids: List[str]):
    """
    Remove records from the collection by ID.
    """
    try:
        res = chroma_db.delete(ids=ids, collection_name=collection_name)
        return {"status": "success", "info": res}
    except Exception as e:
        logger.error(f"Deletion failed: {e}")
        raise HTTPException(status_code=400, detail="Failed to delete specified IDs")

# --- Collection Management Endpoints ---

@router.get("/collections")
async def list_collections():
    """
    List all available collections in the ChromaDB instance.
    """
    try:
        collections = chroma_db.client.list_collections()
        return {"collections": [c.name for c in collections]}
    except Exception as e:
        logger.error(f"Could not list collections: {e}")
        raise HTTPException(status_code=500, detail="Database connection error")

@router.get("/count")
async def get_collection_count(collection_name: str):
    """
    Get the total number of items stored in a collection.
    """
    coll = chroma_db.load_collection(collection_name)
    if coll:
        return {"collection": collection_name, "count": coll.count()}
    raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")

@router.delete("/drop-collection")
async def drop_collection(collection_name: str):
    """
    Completely delete a collection and all its data. Use with caution.
    """
    try:
        chroma_db.client.delete_collection(name=collection_name)
        return {"status": "success", "message": f"Collection '{collection_name}' deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))