namespace DocRag.Models.Dto;

/// <summary>
/// Request for RAG-based question answering.
/// </summary>
public class QueryRequest
{
    /// <summary>
    /// Client ID to filter chunks.
    /// </summary>
    public string? ClientId { get; set; }

    /// <summary>
    /// Question to answer.
    /// </summary>
    public required string Query { get; set; }

    /// <summary>
    /// Maximum number of chunks to use for context.
    /// </summary>
    public int MaxChunks { get; set; } = 5;
}

/// <summary>
/// Response for RAG question answering.
/// </summary>
public class QueryResponse
{
    public string Answer { get; set; } = string.Empty;
    public double Confidence { get; set; }
    public List<SourceChunk> Sources { get; set; } = new();
}

/// <summary>
/// Source chunk used for answering.
/// </summary>
public class SourceChunk
{
    public string ChunkId { get; set; } = string.Empty;
    public string? Heading { get; set; }
    public string ChunkType { get; set; } = string.Empty;
    public string DocumentId { get; set; } = string.Empty;
    public double Rank { get; set; }
}

/// <summary>
/// Chunk search result with ranking.
/// </summary>
public class ChunkSearchResult
{
    public string ChunkId { get; set; } = string.Empty;
    public string DocumentId { get; set; } = string.Empty;
    public string? ClientId { get; set; }
    public string Text { get; set; } = string.Empty;
    public string? Heading { get; set; }
    public string ChunkType { get; set; } = string.Empty;
    public double Rank { get; set; }
}
