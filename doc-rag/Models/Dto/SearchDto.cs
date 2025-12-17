namespace DocRag.Models.Dto;

/// <summary>
/// Request for fulltext search.
/// </summary>
public class SearchRequest
{
    /// <summary>
    /// Client ID to filter documents.
    /// </summary>
    public string? ClientId { get; set; }

    /// <summary>
    /// Search query string.
    /// </summary>
    public required string Query { get; set; }

    /// <summary>
    /// Maximum number of results to return.
    /// </summary>
    public int Limit { get; set; } = 10;
}

/// <summary>
/// Response for fulltext search.
/// </summary>
public class SearchResponse
{
    public string Query { get; set; } = string.Empty;
    public int TotalResults { get; set; }
    public List<SearchResult> Results { get; set; } = new();
}

/// <summary>
/// Single search result item.
/// </summary>
public class SearchResult
{
    public int Id { get; set; }
    public string DocumentId { get; set; } = string.Empty;
    public string? ClientId { get; set; }
    public string? Filename { get; set; }
    public string Snippet { get; set; } = string.Empty;
    public double Rank { get; set; }
}
