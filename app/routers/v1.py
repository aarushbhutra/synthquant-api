"""
API Router for v1 endpoints.
Defines all route handlers for the SynthQuant API.
"""

from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from app.models import (
    StatusResponse,
    ApiKeyVerifyRequest,
    ApiKeyVerifyResponse,
    DatasetCreateRequest,
    DatasetCreateResponse,
    DatasetListResponse,
    DatasetDetailResponse,
    DatasetMetadata,
)
from app.security import (
    check_rate_limit,
    verify_api_key_status,
)
from app.services import (
    generate_dataset,
    get_dataset_preview,
    record_to_metadata,
)
from app.store import store
from app.config import SUPPORTED_FREQUENCIES


# Create router with prefix
router = APIRouter(prefix="/v1", tags=["v1"])


@router.get(
    "/status",
    response_model=StatusResponse,
    summary="Service Status",
    description="Check if the service is running and get current status.",
)
async def get_status() -> StatusResponse:
    """
    Get service status.
    This endpoint does not require authentication.
    """
    return StatusResponse(
        service="ok",
        timestamp=datetime.utcnow().isoformat() + "Z",
        note="Simulation Mode",
    )


@router.post(
    "/apikeys/verify",
    response_model=ApiKeyVerifyResponse,
    summary="Verify API Key",
    description="Verify an API key and check its rate limit status.",
)
async def verify_api_key(request: ApiKeyVerifyRequest) -> ApiKeyVerifyResponse:
    """
    Verify an API key and return its rate limit status.
    This endpoint does not consume rate limit quota.
    """
    is_valid, remaining, limit = verify_api_key_status(request.api_key)
    return ApiKeyVerifyResponse(
        valid=is_valid,
        quota_remaining=remaining,
        limit=limit,
    )


@router.get(
    "/datasets",
    response_model=DatasetListResponse,
    summary="List Datasets",
    description="Get a list of all generated datasets with metadata.",
    dependencies=[Depends(check_rate_limit)],
)
async def list_datasets() -> DatasetListResponse:
    """
    List all datasets stored in memory.
    Requires valid API key and consumes rate limit quota.
    """
    records = store.list_datasets()
    datasets: List[DatasetMetadata] = [record_to_metadata(r) for r in records]
    
    return DatasetListResponse(
        datasets=datasets,
        total_count=len(datasets),
    )


@router.get(
    "/datasets/{dataset_id}",
    response_model=DatasetDetailResponse,
    summary="Get Dataset Details",
    description="Get full metadata and preview for a specific dataset.",
    dependencies=[Depends(check_rate_limit)],
    responses={
        404: {"description": "Dataset not found"},
    },
)
async def get_dataset(dataset_id: str) -> DatasetDetailResponse:
    """
    Get detailed information about a specific dataset.
    Includes metadata and a preview of the first 10 rows.
    """
    record = store.get_dataset(dataset_id)
    
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' not found.",
        )
    
    metadata = record_to_metadata(record)
    preview = get_dataset_preview(record, num_rows=10)
    
    return DatasetDetailResponse(
        metadata=metadata,
        preview=preview,
    )


@router.post(
    "/datasets/create",
    response_model=DatasetCreateResponse,
    summary="Create Dataset",
    description="Generate a new synthetic market dataset using GBM simulation.",
    dependencies=[Depends(check_rate_limit)],
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Invalid request parameters"},
    },
)
async def create_dataset(request: DatasetCreateRequest) -> DatasetCreateResponse:
    """
    Create a new synthetic dataset.
    
    Uses Geometric Brownian Motion (GBM) to generate realistic price paths.
    The seed parameter ensures reproducibility - same parameters will always
    generate the same data.
    """
    # Validate frequency
    if request.frequency not in SUPPORTED_FREQUENCIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid frequency '{request.frequency}'. Supported values: {sorted(SUPPORTED_FREQUENCIES)}",
        )
    
    # Validate assets
    if len(request.assets) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one asset is required.",
        )
    
    # Check for duplicate symbols
    symbols = [a.symbol for a in request.assets]
    if len(symbols) != len(set(symbols)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate asset symbols are not allowed.",
        )
    
    try:
        response = generate_dataset(request)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while generating the dataset: {str(e)}",
        )
