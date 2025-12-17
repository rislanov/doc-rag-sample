using System.Text;
using System.Text.Json;
using DocRag.Models.Dto;

namespace DocRag.Services;

/// <summary>
/// Service for interacting with Ollama LLM.
/// </summary>
public interface IOllamaService
{
    Task<string> GenerateAsync(string prompt, CancellationToken ct = default);
}

public class OllamaService : IOllamaService
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<OllamaService> _logger;
    private readonly string _model;

    public OllamaService(
        HttpClient httpClient,
        ILogger<OllamaService> logger,
        IConfiguration configuration)
    {
        _httpClient = httpClient;
        _logger = logger;
        _model = configuration["Ollama:Model"] ?? "mistral:7b-instruct";
    }

    /// <summary>
    /// Generate text using Ollama API.
    /// </summary>
    public async Task<string> GenerateAsync(string prompt, CancellationToken ct = default)
    {
        _logger.LogInformation("Generating response with model: {Model}", _model);

        var request = new
        {
            model = _model,
            prompt = prompt,
            stream = false,
            options = new
            {
                temperature = 0.7,
                top_p = 0.9,
                num_predict = 1024
            }
        };

        var json = JsonSerializer.Serialize(request);
        var content = new StringContent(json, Encoding.UTF8, "application/json");

        try
        {
            var response = await _httpClient.PostAsync("/api/generate", content, ct);
            response.EnsureSuccessStatusCode();

            var responseBody = await response.Content.ReadAsStringAsync(ct);
            var result = JsonSerializer.Deserialize<OllamaResponse>(responseBody);

            _logger.LogInformation("Generated response of length: {Length}", result?.Response?.Length ?? 0);

            return result?.Response ?? string.Empty;
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "Failed to call Ollama API");
            throw new InvalidOperationException("Failed to generate response from LLM", ex);
        }
    }

    private class OllamaResponse
    {
        public string? Model { get; set; }
        public string? Response { get; set; }
        public bool Done { get; set; }
    }
}
