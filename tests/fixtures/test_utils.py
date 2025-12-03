"""
Shared utility functions for test verification.

This module provides common functions used across multiple test files
for verifying test results and validating expectations.
"""

from typing import Dict, Any, List


def verify_transcription_results(
    transcripts: List[Dict[str, Any]],
    expected: Dict[str, Any]
) -> tuple[bool, str]:
    """
    Verify transcription results against expected criteria.
    
    Args:
        transcripts: List of transcription results
        expected: Expected criteria for verification
        
    Returns:
        Tuple of (success, message)
    """
    # Check minimum number of transcripts
    if len(transcripts) < expected["min_length"]:
        return False, f"Expected at least {expected['min_length']} transcripts, got {len(transcripts)}"
    
    # Check transcript structure and content
    for transcript in transcripts:
        # Check required fields
        for field in expected["expected_fields"]:
            if field not in transcript:
                return False, f"Missing required field '{field}' in transcript"
        
        # Check transcript content
        if "transcript" in transcript:
            if len(transcript["transcript"]) < expected["min_transcript_length"]:
                return False, f"Transcript text too short: '{transcript['transcript']}'"
    
    # Check that we have at least one final transcript
    has_final_transcript = any(t.get("is_final", False) for t in transcripts)
    if not has_final_transcript:
        return False, "No final transcript received"
    
    return True, "All verification passed"


def get_final_transcripts(transcripts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract final transcripts from a list of transcription results.
    
    Args:
        transcripts: List of all transcription results
        
    Returns:
        List of final transcripts only
    """
    return [t for t in transcripts if t.get("is_final", False)]


def verify_audio_chunks(chunks: List[bytes], min_chunks: int = 1) -> tuple[bool, str]:
    """
    Verify audio chunks meet basic requirements.
    
    Args:
        chunks: List of audio chunks
        min_chunks: Minimum number of chunks expected
        
    Returns:
        Tuple of (success, message)
    """
    if len(chunks) < min_chunks:
        return False, f"Expected at least {min_chunks} chunks, got {len(chunks)}"
    
    total_size = sum(len(chunk) for chunk in chunks)
    if total_size == 0:
        return False, "No audio data received"
    
    return True, f"Received {len(chunks)} chunks with {total_size:,} bytes total"
