using System.Text;
using DocRag.Models.Dto;

namespace DocRag.Services;

/// <summary>
/// RAG-based question answering service with hybrid search.
/// </summary>
public interface IQaService
{
    Task<QueryResponse> AnswerQuestionAsync(QueryRequest request, CancellationToken ct = default);
}

public class QaService : IQaService
{
    private readonly ISearchService _searchService;
    private readonly IEmbeddingService _embeddingService;
    private readonly IOllamaService _ollamaService;
    private readonly ILogger<QaService> _logger;
    private readonly int _minQueryLength;
    private readonly bool _useHybridSearch;

    public QaService(
        ISearchService searchService,
        IEmbeddingService embeddingService,
        IOllamaService ollamaService,
        ILogger<QaService> logger,
        IConfiguration configuration)
    {
        _searchService = searchService;
        _embeddingService = embeddingService;
        _ollamaService = ollamaService;
        _logger = logger;
        _minQueryLength = configuration.GetValue<int>("Search:MinQueryLength", 3);
        _useHybridSearch = configuration.GetValue<bool>("Search:UseHybridSearch", true);
    }

    /// <summary>
    /// Answer a question using RAG approach with hybrid search.
    /// </summary>
    public async Task<QueryResponse> AnswerQuestionAsync(QueryRequest request, CancellationToken ct = default)
    {
        // Validate query
        if (string.IsNullOrWhiteSpace(request.Query) || request.Query.Length < _minQueryLength)
        {
            throw new ArgumentException($"Query must be at least {_minQueryLength} characters");
        }

        _logger.LogInformation("Processing question: {Query}, HybridSearch: {Hybrid}", request.Query, _useHybridSearch);

        List<ChunkSearchResult> chunks;

        if (_useHybridSearch)
        {
            // Get query embedding for semantic search
            var queryEmbedding = await _embeddingService.GetEmbeddingAsync(request.Query, ct);
            
            // Hybrid search (fulltext + semantic with RRF fusion)
            chunks = await _searchService.SearchChunksHybridAsync(
                request.Query,
                queryEmbedding,
                request.ClientId,
                request.MaxChunks > 0 ? request.MaxChunks : 5,
                ct
            );
        }
        else
        {
            // Fallback to fulltext-only search
            chunks = await _searchService.SearchChunksAsync(
                request.Query,
                request.ClientId,
                request.MaxChunks > 0 ? request.MaxChunks : 5,
                ct
            );
        }

        // If no chunks found, return empty response
        if (chunks.Count == 0)
        {
            _logger.LogInformation("No relevant chunks found for query: {Query}", request.Query);
            return new QueryResponse
            {
                Answer = "К сожалению, информация по вашему запросу не найдена в документах.",
                Confidence = 0.1,
                Sources = new List<SourceChunk>()
            };
        }

        // Build prompt with context
        var prompt = BuildPrompt(request.Query, chunks);

        // Generate answer using LLM
        var answer = await _ollamaService.GenerateAsync(prompt, ct);

        // Calculate confidence based on chunk ranks
        var confidence = CalculateConfidence(chunks, answer);

        // Build sources list
        var sources = chunks.Select(c => new SourceChunk
        {
            ChunkId = c.ChunkId,
            Heading = c.Heading,
            ChunkType = c.ChunkType,
            DocumentId = c.DocumentId,
            Rank = c.Rank
        }).ToList();

        _logger.LogInformation("Generated answer with confidence: {Confidence}", confidence);

        return new QueryResponse
        {
            Answer = answer.Trim(),
            Confidence = confidence,
            Sources = sources
        };
    }

    /// <summary>
    /// Build prompt for LLM with context chunks.
    /// </summary>
    private static string BuildPrompt(string query, List<ChunkSearchResult> chunks)
    {
        var sb = new StringBuilder();

        sb.AppendLine("Ты — помощник по анализу документов. Отвечай на русском языке.");
        sb.AppendLine();
        sb.AppendLine("## Контекст из документов:");
        sb.AppendLine();

        for (int i = 0; i < chunks.Count; i++)
        {
            var chunk = chunks[i];
            sb.AppendLine($"### Фрагмент {i + 1} (релевантность: {chunk.Rank:F2})");
            
            if (!string.IsNullOrEmpty(chunk.Heading))
            {
                sb.AppendLine($"**Раздел:** {chunk.Heading}");
            }
            
            // Truncate long chunks for prompt
            var text = chunk.Text.Length > 500 ? chunk.Text[..500] + "..." : chunk.Text;
            sb.AppendLine(text);
            sb.AppendLine();
        }

        sb.AppendLine("---");
        sb.AppendLine();
        sb.AppendLine($"**Вопрос:** {query}");
        sb.AppendLine();
        sb.AppendLine("Отвечай на основе предоставленных документов. Если информации недостаточно, скажи об этом.");
        sb.AppendLine();
        sb.AppendLine("**Ответ:**");

        return sb.ToString();
    }

    /// <summary>
    /// Calculate confidence score based on chunk ranks and answer quality.
    /// </summary>
    private static double CalculateConfidence(List<ChunkSearchResult> chunks, string answer)
    {
        if (chunks.Count == 0 || string.IsNullOrEmpty(answer))
        {
            return 0.1;
        }

        // Base confidence from average rank
        var avgRank = chunks.Average(c => c.Rank);
        
        // Bonus for longer, more detailed answers
        var lengthBonus = answer.Length > 100 ? 0.1 : 0.0;
        
        // Bonus for multiple sources
        var sourcesBonus = chunks.Count >= 3 ? 0.1 : 0.0;

        var confidence = 0.5 + (avgRank * 0.3) + lengthBonus + sourcesBonus;

        // Clamp to 0-1 range
        return Math.Clamp(confidence, 0.1, 0.95);
    }
}
