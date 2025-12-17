using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Pgvector;

namespace DocRag.Services;

/// <summary>
/// Service for generating embeddings via Ollama.
/// </summary>
public interface IEmbeddingService
{
    Task<Vector?> GetEmbeddingAsync(string text, CancellationToken ct = default);
    Task<List<Vector?>> GetEmbeddingsAsync(IEnumerable<string> texts, CancellationToken ct = default);
}

public class OllamaEmbeddingService : IEmbeddingService
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<OllamaEmbeddingService> _logger;
    private readonly string _model;

    public OllamaEmbeddingService(
        HttpClient httpClient,
        ILogger<OllamaEmbeddingService> logger,
        IConfiguration configuration)
    {
        _httpClient = httpClient;
        _logger = logger;
        _model = configuration["Ollama:EmbeddingModel"] ?? "nomic-embed-text";
    }

    /// <summary>
    /// Generate embedding for a single text.
    /// </summary>
    public async Task<Vector?> GetEmbeddingAsync(string text, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(text))
            return null;

        try
        {
            var request = new
            {
                model = _model,
                prompt = text.Length > 8000 ? text[..8000] : text
            };

            var json = JsonSerializer.Serialize(request);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync("/api/embeddings", content, ct);
            response.EnsureSuccessStatusCode();

            var responseBody = await response.Content.ReadAsStringAsync(ct);
            var result = JsonSerializer.Deserialize<EmbeddingResponse>(responseBody);

            if (result?.Embedding != null && result.Embedding.Length > 0)
            {
                _logger.LogDebug("Generated embedding of dimension {Dim}", result.Embedding.Length);
                return new Vector(result.Embedding);
            }

            return null;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to generate embedding for text of length {Length}", text.Length);
            return null;
        }
    }

    /// <summary>
    /// Generate embeddings for multiple texts.
    /// </summary>
    public async Task<List<Vector?>> GetEmbeddingsAsync(IEnumerable<string> texts, CancellationToken ct = default)
    {
        var results = new List<Vector?>();
        
        foreach (var text in texts)
        {
            var embedding = await GetEmbeddingAsync(text, ct);
            results.Add(embedding);
        }

        return results;
    }

    private class EmbeddingResponse
    {
        [JsonPropertyName("embedding")]
        public float[]? Embedding { get; set; }
    }
}
