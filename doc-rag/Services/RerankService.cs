using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace DocRag.Services;

/// <summary>
/// Re-ranking service using Cross-Encoder model for fast, accurate relevance scoring.
/// Calls external Python microservice with BAAI/bge-reranker-v2-m3 model.
/// </summary>
public interface IRerankService
{
    /// <summary>
    /// Re-rank search results by relevance to query.
    /// </summary>
    Task<List<RankedChunk>> RerankAsync(
        string query, 
        List<SearchChunkResult> candidates, 
        int topK = 5,
        CancellationToken cancellationToken = default);
}

/// <summary>
/// Result after re-ranking with relevance score.
/// </summary>
public class RankedChunk
{
    public SearchChunkResult Chunk { get; set; } = null!;
    public float RelevanceScore { get; set; }
    public string Reasoning { get; set; } = "";
}

public class RerankService : IRerankService
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<RerankService> _logger;
    private readonly bool _enabled;
    private readonly string _baseUrl;
    private readonly int _timeoutSeconds;

    public RerankService(
        IHttpClientFactory httpClientFactory, 
        ILogger<RerankService> logger,
        IConfiguration configuration)
    {
        _httpClient = httpClientFactory.CreateClient("Reranker");
        _logger = logger;
        _enabled = configuration.GetValue("Reranker:Enabled", true);
        _baseUrl = configuration.GetValue("Reranker:BaseUrl", "http://reranker:8000") ?? "http://reranker:8000";
        _timeoutSeconds = configuration.GetValue("Reranker:TimeoutSeconds", 30);
    }

    public async Task<List<RankedChunk>> RerankAsync(
        string query, 
        List<SearchChunkResult> candidates, 
        int topK = 5,
        CancellationToken cancellationToken = default)
    {
        if (!_enabled || candidates.Count == 0)
        {
            // Return original order with default scores
            return candidates
                .Take(topK)
                .Select((c, i) => new RankedChunk 
                { 
                    Chunk = c, 
                    RelevanceScore = 1.0f - (i * 0.1f),
                    Reasoning = "Re-ranking disabled"
                })
                .ToList();
        }

        if (candidates.Count <= topK)
        {
            // Not enough candidates, still rerank for accurate scores
            topK = candidates.Count;
        }

        _logger.LogInformation(
            "Re-ranking {Count} candidates for query: {Query}", 
            candidates.Count, 
            query.Length > 50 ? query[..50] + "..." : query);

        try
        {
            var result = await CallRerankerServiceAsync(query, candidates, topK, cancellationToken);

            _logger.LogInformation(
                "Re-ranking complete. Top score: {TopScore:F3}, Bottom score: {BottomScore:F3}",
                result.FirstOrDefault()?.RelevanceScore ?? 0,
                result.LastOrDefault()?.RelevanceScore ?? 0);

            return result;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Re-ranking failed, returning original order");
            return candidates
                .Take(topK)
                .Select((c, i) => new RankedChunk 
                { 
                    Chunk = c, 
                    RelevanceScore = 1.0f - (i * 0.05f),
                    Reasoning = "Re-ranking failed"
                })
                .ToList();
        }
    }

    private async Task<List<RankedChunk>> CallRerankerServiceAsync(
        string query,
        List<SearchChunkResult> candidates,
        int topK,
        CancellationToken cancellationToken)
    {
        // Build request for reranker service
        var request = new RerankerRequest
        {
            Query = query,
            Documents = candidates.Select(c => new RerankerDocument
            {
                Id = c.ChunkId.ToString(),
                Content = c.Content,
                Metadata = new Dictionary<string, string>
                {
                    ["filename"] = c.Filename ?? "",
                    ["section"] = c.SectionHeader ?? "",
                    ["chunk_type"] = c.ChunkType ?? ""
                }
            }).ToList(),
            TopK = topK
        };

        var json = JsonSerializer.Serialize(request, _jsonOptions);
        var content = new StringContent(json, Encoding.UTF8, "application/json");

        using var cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        cts.CancelAfter(TimeSpan.FromSeconds(_timeoutSeconds));

        var response = await _httpClient.PostAsync(
            $"{_baseUrl}/rerank", 
            content, 
            cts.Token);

        response.EnsureSuccessStatusCode();

        var responseJson = await response.Content.ReadAsStringAsync(cts.Token);
        var rerankerResponse = JsonSerializer.Deserialize<RerankerResponse>(responseJson, _jsonOptions);

        if (rerankerResponse?.Results == null)
        {
            throw new InvalidOperationException("Invalid response from reranker service");
        }

        // Map back to RankedChunk objects
        var candidatesById = candidates.ToDictionary(c => c.ChunkId.ToString());
        var results = new List<RankedChunk>();

        foreach (var result in rerankerResponse.Results)
        {
            if (candidatesById.TryGetValue(result.Id, out var chunk))
            {
                results.Add(new RankedChunk
                {
                    Chunk = chunk,
                    RelevanceScore = result.Score,
                    Reasoning = $"Cross-Encoder score: {result.Score:F3}"
                });
            }
        }

        return results;
    }

    private static readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    #region Request/Response DTOs

    private class RerankerRequest
    {
        public string Query { get; set; } = "";
        public List<RerankerDocument> Documents { get; set; } = new();
        public int TopK { get; set; } = 5;
    }

    private class RerankerDocument
    {
        public string Id { get; set; } = "";
        public string Content { get; set; } = "";
        public Dictionary<string, string>? Metadata { get; set; }
    }

    private class RerankerResponse
    {
        public List<RerankerResult> Results { get; set; } = new();
        public string? Model { get; set; }
        public float ProcessingTimeMs { get; set; }
    }

    private class RerankerResult
    {
        public string Id { get; set; } = "";
        public float Score { get; set; }
        public int OriginalIndex { get; set; }
    }

    #endregion
}

/// <summary>
/// Search result from SearchService (to avoid circular dependency).
/// </summary>
public class SearchChunkResult
{
    public int ChunkId { get; set; }
    public int DocumentId { get; set; }
    public string Content { get; set; } = "";
    public string? SectionHeader { get; set; }
    public string? ChunkType { get; set; }
    public string? Filename { get; set; }
    public string? Headline { get; set; }
    public float Rank { get; set; }
}
