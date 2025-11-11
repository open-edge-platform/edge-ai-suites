# tests/test_milvus_utils.py

import sys
import os
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch, call

# Add the src directory to Python path
src_path = Path(__file__).parent.parent / "src" / "feature-matching"
sys.path.insert(0, str(src_path))

# Import the module to test
from milvus_utils import (
    CollectionExists,
    get_milvus_client,
    create_collection,
    get_search_results
)


class TestCollectionExists:
    """Test cases for CollectionExists exception"""
    
    def test_collection_exists_is_runtime_error(self):
        """Test that CollectionExists inherits from RuntimeError"""
        assert issubclass(CollectionExists, RuntimeError)
    
    def test_collection_exists_can_be_raised(self):
        """Test that CollectionExists can be raised and caught"""
        with pytest.raises(CollectionExists) as exc_info:
            raise CollectionExists("Test collection exists")
        
        assert "Test collection exists" in str(exc_info.value)
    
    def test_collection_exists_message(self):
        """Test CollectionExists with custom message"""
        error_message = "Collection 'my_collection' already exists"
        
        with pytest.raises(CollectionExists) as exc_info:
            raise CollectionExists(error_message)
        
        assert error_message == str(exc_info.value)


class TestGetMilvusClient:
    """Test cases for get_milvus_client function"""
    
    @patch('milvus_utils.MilvusClient')
    def test_get_milvus_client_with_uri_only(self, mock_milvus_client):
        """Test creating Milvus client with URI only"""
        uri = "http://localhost:19530"
        mock_client_instance = MagicMock()
        mock_milvus_client.return_value = mock_client_instance
        
        result = get_milvus_client(uri=uri)
        
        mock_milvus_client.assert_called_once_with(uri=uri, token=None)
        assert result == mock_client_instance
    
    @patch('milvus_utils.MilvusClient')
    def test_get_milvus_client_with_uri_and_token(self, mock_milvus_client):
        """Test creating Milvus client with URI and token"""
        uri = "http://localhost:19530"
        token = "my_secret_token"
        mock_client_instance = MagicMock()
        mock_milvus_client.return_value = mock_client_instance
        
        result = get_milvus_client(uri=uri, token=token)
        
        mock_milvus_client.assert_called_once_with(uri=uri, token=token)
        assert result == mock_client_instance
    
    @patch('milvus_utils.MilvusClient')
    def test_get_milvus_client_with_none_token(self, mock_milvus_client):
        """Test creating Milvus client with explicit None token"""
        uri = "http://localhost:19530"
        mock_client_instance = MagicMock()
        mock_milvus_client.return_value = mock_client_instance
        
        result = get_milvus_client(uri=uri, token=None)
        
        mock_milvus_client.assert_called_once_with(uri=uri, token=None)
        assert result == mock_client_instance
    
    @patch('milvus_utils.MilvusClient')
    def test_get_milvus_client_returns_client_instance(self, mock_milvus_client):
        """Test that get_milvus_client returns the correct client instance"""
        uri = "http://test.milvus.io:19530"
        token = "test_token"
        mock_client_instance = MagicMock()
        mock_client_instance.some_method = MagicMock(return_value="test")
        mock_milvus_client.return_value = mock_client_instance
        
        result = get_milvus_client(uri=uri, token=token)
        
        # Verify we can call methods on the returned client
        assert result.some_method() == "test"


class TestCreateCollection:
    """Test cases for create_collection function"""
    
    def test_create_collection_new_collection(self):
        """Test creating a new collection when it doesn't exist"""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = False
        mock_client.create_collection.return_value = {"status": "created"}
        
        collection_name = "test_collection"
        dim = 512
        
        result = create_collection(
            milvus_client=mock_client,
            collection_name=collection_name,
            dim=dim,
            drop_old=True
        )
        
        # Verify has_collection was called once
        mock_client.has_collection.assert_called_once_with(collection_name)
        
        # Verify drop_collection was NOT called
        mock_client.drop_collection.assert_not_called()
        
        # Verify create_collection was called with correct params
        mock_client.create_collection.assert_called_once_with(
            collection_name=collection_name,
            dimension=dim,
            metric_type="COSINE",
            consistency_level="Strong",
            auto_id=True
        )
        
        assert result == {"status": "created"}
    
    def test_create_collection_drop_existing(self):
        """Test creating collection with drop_old=True drops existing collection"""
        mock_client = MagicMock()
        # First call returns True (collection exists), second call returns False (after drop)
        mock_client.has_collection.side_effect = [True, False]
        mock_client.create_collection.return_value = {"status": "created"}
        
        collection_name = "existing_collection"
        dim = 768
        
        result = create_collection(
            milvus_client=mock_client,
            collection_name=collection_name,
            dim=dim,
            drop_old=True
        )
        
        # Verify has_collection was called twice
        assert mock_client.has_collection.call_count == 2
        
        # Verify drop_collection was called
        mock_client.drop_collection.assert_called_once_with(collection_name)
        
        # Verify create_collection was called
        mock_client.create_collection.assert_called_once()
        
        assert result == {"status": "created"}
    
    def test_create_collection_exists_no_drop(self):
        """Test that CollectionExists is raised when collection exists and drop_old=False"""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        
        collection_name = "existing_collection"
        dim = 512
        
        with pytest.raises(CollectionExists) as exc_info:
            create_collection(
                milvus_client=mock_client,
                collection_name=collection_name,
                dim=dim,
                drop_old=False
            )
        
        # Verify the error message
        expected_message = f"Collection {collection_name} already exists. Set drop_old=True to create a new one instead."
        assert expected_message in str(exc_info.value)
        
        # Verify drop_collection was NOT called
        mock_client.drop_collection.assert_not_called()
        
        # Verify create_collection was NOT called
        mock_client.create_collection.assert_not_called()
    
    def test_create_collection_with_different_dimensions(self):
        """Test creating collections with different dimensions"""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = False
        mock_client.create_collection.return_value = {"status": "created"}
        
        dimensions = [128, 256, 512, 768, 1024, 2048]
        
        for dim in dimensions:
            mock_client.reset_mock()
            
            result = create_collection(
                milvus_client=mock_client,
                collection_name=f"collection_{dim}",
                dim=dim,
                drop_old=True
            )
            
            # Verify dimension is passed correctly
            call_kwargs = mock_client.create_collection.call_args[1]
            assert call_kwargs['dimension'] == dim
    
    def test_create_collection_default_drop_old_true(self):
        """Test that drop_old defaults to True"""
        mock_client = MagicMock()
        mock_client.has_collection.side_effect = [True, False]
        mock_client.create_collection.return_value = {"status": "created"}
        
        collection_name = "test_collection"
        dim = 512
        
        # Call without specifying drop_old (should default to True)
        result = create_collection(
            milvus_client=mock_client,
            collection_name=collection_name,
            dim=dim
        )
        
        # Should drop the existing collection
        mock_client.drop_collection.assert_called_once()
    
    def test_create_collection_metric_type_cosine(self):
        """Test that metric_type is always COSINE"""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = False
        mock_client.create_collection.return_value = {"status": "created"}
        
        create_collection(
            milvus_client=mock_client,
            collection_name="test",
            dim=512,
            drop_old=True
        )
        
        call_kwargs = mock_client.create_collection.call_args[1]
        assert call_kwargs['metric_type'] == "COSINE"
    
    def test_create_collection_consistency_level_strong(self):
        """Test that consistency_level is always Strong"""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = False
        mock_client.create_collection.return_value = {"status": "created"}
        
        create_collection(
            milvus_client=mock_client,
            collection_name="test",
            dim=512,
            drop_old=True
        )
        
        call_kwargs = mock_client.create_collection.call_args[1]
        assert call_kwargs['consistency_level'] == "Strong"
    
    def test_create_collection_auto_id_true(self):
        """Test that auto_id is always True"""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = False
        mock_client.create_collection.return_value = {"status": "created"}
        
        create_collection(
            milvus_client=mock_client,
            collection_name="test",
            dim=512,
            drop_old=True
        )
        
        call_kwargs = mock_client.create_collection.call_args[1]
        assert call_kwargs['auto_id'] is True
    
    def test_create_collection_returns_result(self):
        """Test that create_collection returns the result from MilvusClient"""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = False
        expected_result = {"collection_name": "test", "status": "success", "id": 12345}
        mock_client.create_collection.return_value = expected_result
        
        result = create_collection(
            milvus_client=mock_client,
            collection_name="test",
            dim=512
        )
        
        assert result == expected_result


class TestGetSearchResults:
    """Test cases for get_search_results function"""
    
    def test_get_search_results_basic(self):
        """Test basic search results retrieval"""
        mock_client = MagicMock()
        expected_results = [
            {"id": 1, "filename": "image1.jpg", "label": "person", "distance": 0.95},
            {"id": 2, "filename": "image2.jpg", "label": "car", "distance": 0.87}
        ]
        mock_client.search.return_value = expected_results
        
        collection_name = "test_collection"
        query_vector = [0.1, 0.2, 0.3, 0.4]
        output_fields = ["filename", "label", "timestamp"]
        
        result = get_search_results(
            milvus_client=mock_client,
            collection_name=collection_name,
            query_vector=query_vector,
            output_fields=output_fields
        )
        
        # Verify search was called with correct params
        mock_client.search.assert_called_once_with(
            collection_name=collection_name,
            data=[query_vector],
            search_params={"metric_type": "COSINE", "params": {}},
            output_fields=output_fields
        )
        
        assert result == expected_results
    
    def test_get_search_results_wraps_query_vector_in_list(self):
        """Test that query_vector is wrapped in a list"""
        mock_client = MagicMock()
        mock_client.search.return_value = []
        
        query_vector = [0.5] * 512
        
        get_search_results(
            milvus_client=mock_client,
            collection_name="test",
            query_vector=query_vector,
            output_fields=["id"]
        )
        
        # Verify the query_vector was wrapped in a list
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs['data'] == [query_vector]
        assert isinstance(call_kwargs['data'], list)
        assert len(call_kwargs['data']) == 1
    
    def test_get_search_results_metric_type_cosine(self):
        """Test that search uses COSINE metric type"""
        mock_client = MagicMock()
        mock_client.search.return_value = []
        
        get_search_results(
            milvus_client=mock_client,
            collection_name="test",
            query_vector=[0.1, 0.2],
            output_fields=["id"]
        )
        
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs['search_params']['metric_type'] == "COSINE"
    
    def test_get_search_results_empty_search_params(self):
        """Test that search_params has empty params dict"""
        mock_client = MagicMock()
        mock_client.search.return_value = []
        
        get_search_results(
            milvus_client=mock_client,
            collection_name="test",
            query_vector=[0.1],
            output_fields=["id"]
        )
        
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs['search_params']['params'] == {}
    
    def test_get_search_results_multiple_output_fields(self):
        """Test search with multiple output fields"""
        mock_client = MagicMock()
        mock_client.search.return_value = []
        
        output_fields = ["id", "filename", "label", "timestamp", "confidence", "metadata"]
        
        get_search_results(
            milvus_client=mock_client,
            collection_name="test",
            query_vector=[0.1] * 512,
            output_fields=output_fields
        )
        
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs['output_fields'] == output_fields
    
    def test_get_search_results_single_output_field(self):
        """Test search with single output field"""
        mock_client = MagicMock()
        mock_client.search.return_value = []
        
        output_fields = ["filename"]
        
        get_search_results(
            milvus_client=mock_client,
            collection_name="test",
            query_vector=[0.5] * 128,
            output_fields=output_fields
        )
        
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs['output_fields'] == output_fields
    
    def test_get_search_results_returns_search_results(self):
        """Test that function returns search results from MilvusClient"""
        mock_client = MagicMock()
        
        expected_results = [
            [
                {"id": 1, "distance": 0.99, "entity": {"filename": "test1.jpg"}},
                {"id": 2, "distance": 0.85, "entity": {"filename": "test2.jpg"}},
                {"id": 3, "distance": 0.72, "entity": {"filename": "test3.jpg"}}
            ]
        ]
        mock_client.search.return_value = expected_results
        
        result = get_search_results(
            milvus_client=mock_client,
            collection_name="test",
            query_vector=[0.1] * 256,
            output_fields=["filename", "label"]
        )
        
        assert result == expected_results
    
    def test_get_search_results_empty_results(self):
        """Test search that returns empty results"""
        mock_client = MagicMock()
        mock_client.search.return_value = []
        
        result = get_search_results(
            milvus_client=mock_client,
            collection_name="test",
            query_vector=[0.1] * 512,
            output_fields=["id"]
        )
        
        assert result == []
    
    def test_get_search_results_with_different_vector_dimensions(self):
        """Test search with different vector dimensions"""
        mock_client = MagicMock()
        mock_client.search.return_value = []
        
        dimensions = [128, 256, 512, 768, 1024]
        
        for dim in dimensions:
            mock_client.reset_mock()
            query_vector = [0.1] * dim
            
            get_search_results(
                milvus_client=mock_client,
                collection_name=f"collection_{dim}",
                query_vector=query_vector,
                output_fields=["id"]
            )
            
            # Verify the vector dimension is preserved
            call_kwargs = mock_client.search.call_args[1]
            assert len(call_kwargs['data'][0]) == dim


class TestIntegration:
    """Integration tests for milvus_utils functions"""
    
    @patch('milvus_utils.MilvusClient')
    def test_full_workflow(self, mock_milvus_client_class):
        """Test complete workflow: create client, create collection, search"""
        # Setup mock client
        mock_client = MagicMock()
        mock_milvus_client_class.return_value = mock_client
        mock_client.has_collection.return_value = False
        mock_client.create_collection.return_value = {"status": "created"}
        mock_client.search.return_value = [
            {"id": 1, "filename": "result1.jpg", "distance": 0.95}
        ]
        
        # Step 1: Create client
        uri = "http://localhost:19530"
        token = "test_token"
        client = get_milvus_client(uri=uri, token=token)
        
        # Step 2: Create collection
        collection_name = "test_collection"
        dim = 512
        create_collection(
            milvus_client=client,
            collection_name=collection_name,
            dim=dim,
            drop_old=True
        )
        
        # Step 3: Search
        query_vector = [0.1] * dim
        output_fields = ["filename", "label", "timestamp"]
        results = get_search_results(
            milvus_client=client,
            collection_name=collection_name,
            query_vector=query_vector,
            output_fields=output_fields
        )
        
        # Verify all steps
        mock_milvus_client_class.assert_called_once_with(uri=uri, token=token)
        mock_client.create_collection.assert_called_once()
        mock_client.search.assert_called_once()
        assert len(results) == 1
    
    def test_collection_exists_error_handling(self):
        """Test proper error handling when collection exists"""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        
        collection_name = "existing_collection"
        
        # First attempt: drop_old=False should raise error
        with pytest.raises(CollectionExists):
            create_collection(
                milvus_client=mock_client,
                collection_name=collection_name,
                dim=512,
                drop_old=False
            )
        
        # Second attempt: drop_old=True should succeed
        mock_client.has_collection.side_effect = [True, False]
        mock_client.create_collection.return_value = {"status": "created"}
        
        result = create_collection(
            milvus_client=mock_client,
            collection_name=collection_name,
            dim=512,
            drop_old=True
        )
        
        assert result == {"status": "created"}


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_create_collection_with_small_dimension(self):
        """Test creating collection with minimum dimension"""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = False
        mock_client.create_collection.return_value = {"status": "created"}
        
        result = create_collection(
            milvus_client=mock_client,
            collection_name="small_dim_collection",
            dim=1  # Minimum dimension
        )
        
        call_kwargs = mock_client.create_collection.call_args[1]
        assert call_kwargs['dimension'] == 1
    
    def test_create_collection_with_large_dimension(self):
        """Test creating collection with large dimension"""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = False
        mock_client.create_collection.return_value = {"status": "created"}
        
        large_dim = 32768
        result = create_collection(
            milvus_client=mock_client,
            collection_name="large_dim_collection",
            dim=large_dim
        )
        
        call_kwargs = mock_client.create_collection.call_args[1]
        assert call_kwargs['dimension'] == large_dim
    
    def test_get_search_results_with_empty_output_fields(self):
        """Test search with empty output fields list"""
        mock_client = MagicMock()
        mock_client.search.return_value = []
        
        result = get_search_results(
            milvus_client=mock_client,
            collection_name="test",
            query_vector=[0.1] * 512,
            output_fields=[]
        )
        
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs['output_fields'] == []
    
    def test_get_search_results_with_special_collection_name(self):
        """Test search with special characters in collection name"""
        mock_client = MagicMock()
        mock_client.search.return_value = []
        
        special_names = [
            "collection_with_underscore",
            "collection-with-dash",
            "collection123",
            "Collection_2024"
        ]
        
        for name in special_names:
            mock_client.reset_mock()
            
            get_search_results(
                milvus_client=mock_client,
                collection_name=name,
                query_vector=[0.1],
                output_fields=["id"]
            )
            
            call_kwargs = mock_client.search.call_args[1]
            assert call_kwargs['collection_name'] == name
    
    def test_get_milvus_client_with_different_uris(self):
        """Test client creation with various URI formats"""
        from feature_matching.milvus_utils import get_milvus_client
        
        uris = [
            "http://localhost:19530",
            "https://remote-milvus.example.com:19530",
            "milvus://localhost:19530",
            "192.168.1.100:19530"
        ]
        
        with patch('feature_matching.milvus_utils.MilvusClient') as mock_client_class:
            for uri in uris:
                mock_client_class.reset_mock()
                
                get_milvus_client(uri=uri)
                
                call_kwargs = mock_client_class.call_args[1]
                assert call_kwargs['uri'] == uri
