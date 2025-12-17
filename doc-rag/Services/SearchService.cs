using Microsoft.EntityFrameworkCore;
using Npgsql;
using DocRag.Data;
using DocRag.Models.Dto;
using Pgvector;

namespace DocRag.Services;

/// <summary>
/// Service for fulltext and semantic search using PostgreSQL.
/// </summary>
public interface ISearchService
{
    Task<SearchResponse> SearchDocumentsAsync(SearchRequest request, CancellationToken ct = default);
    Task<List<ChunkSearchResult>> SearchChunksAsync(string query, string? clientId, int limit, CancellationToken ct = default);
    Task<List<ChunkSearchResult>> SearchChunksSemanticAsync(Vector queryEmbedding, string? clientId, int limit, CancellationToken ct = default);
    Task<List<ChunkSearchResult>> SearchChunksHybridAsync(string query, Vector? queryEmbedding, string? clientId, int limit, CancellationToken ct = default);
}

public class SearchService : ISearchService
{
    private readonly DocRagDbContext _context;
    private readonly ILogger<SearchService> _logger;
    private readonly int _defaultLimit;

    public SearchService(
        DocRagDbContext context,
        ILogger<SearchService> logger,
        IConfiguration configuration)
    {
        _context = context;
        _logger = logger;
        _defaultLimit = configuration.GetValue<int>("Search:DefaultLimit", 10);
    }

    /// <summary>
    /// Search documents using PostgreSQL fulltext search.
    /// </summary>
    public async Task<SearchResponse> SearchDocumentsAsync(SearchRequest request, CancellationToken ct = default)
    {
        var limit = request.Limit > 0 ? request.Limit : _defaultLimit;
        var query = PreprocessQuery(request.Query);

        _logger.LogInformation("Searching documents for query: {Query}, ClientId: {ClientId}", 
            query, request.ClientId);

        var sql = @"
            SELECT 
                id,
                document_id,
                client_id,
                filename,
                ts_headline('russian', fulltext, plainto_tsquery('russian', @query), 
                    'MaxWords=50, MinWords=25, StartSel=<b>, StopSel=</b>') as snippet,
                ts_rank(to_tsvector('russian', fulltext), plainto_tsquery('russian', @query)) as rank
            FROM documents
            WHERE to_tsvector('russian', fulltext) @@ plainto_tsquery('russian', @query)
            " + (string.IsNullOrEmpty(request.ClientId) ? "" : "AND client_id = @clientId") + @"
            ORDER BY rank DESC
            LIMIT @limit";

        var results = new List<SearchResult>();

        await using var connection = (NpgsqlConnection)_context.Database.GetDbConnection();
        await connection.OpenAsync(ct);

        await using var command = new NpgsqlCommand(sql, connection);
        command.Parameters.AddWithValue("@query", query);
        command.Parameters.AddWithValue("@limit", limit);
        
        if (!string.IsNullOrEmpty(request.ClientId))
        {
            command.Parameters.AddWithValue("@clientId", request.ClientId);
        }

        await using var reader = await command.ExecuteReaderAsync(ct);
        
        while (await reader.ReadAsync(ct))
        {
            results.Add(new SearchResult
            {
                Id = reader.GetInt32(0),
                DocumentId = reader.GetString(1),
                ClientId = reader.IsDBNull(2) ? null : reader.GetString(2),
                Filename = reader.IsDBNull(3) ? null : reader.GetString(3),
                Snippet = reader.IsDBNull(4) ? "" : reader.GetString(4),
                Rank = reader.GetDouble(5)
            });
        }

        _logger.LogInformation("Found {Count} documents for query: {Query}", results.Count, query);

        return new SearchResponse
        {
            Query = request.Query,
            TotalResults = results.Count,
            Results = results
        };
    }

    /// <summary>
    /// Search chunks for RAG context using PostgreSQL fulltext search.
    /// </summary>
    public async Task<List<ChunkSearchResult>> SearchChunksAsync(
        string query, 
        string? clientId, 
        int limit, 
        CancellationToken ct = default)
    {
        var processedQuery = PreprocessQuery(query);

        _logger.LogInformation("Searching chunks for query: {Query}, ClientId: {ClientId}", 
            processedQuery, clientId);

        var sql = @"
            SELECT 
                chunk_id,
                document_id,
                client_id,
                text,
                heading,
                chunk_type,
                ts_rank(to_tsvector('russian', text), plainto_tsquery('russian', @query)) as rank
            FROM chunks
            WHERE to_tsvector('russian', text) @@ plainto_tsquery('russian', @query)
            " + (string.IsNullOrEmpty(clientId) ? "" : "AND client_id = @clientId") + @"
            ORDER BY rank DESC, chunk_index ASC
            LIMIT @limit";

        var results = new List<ChunkSearchResult>();

        await using var connection = (NpgsqlConnection)_context.Database.GetDbConnection();
        await connection.OpenAsync(ct);

        await using var command = new NpgsqlCommand(sql, connection);
        command.Parameters.AddWithValue("@query", processedQuery);
        command.Parameters.AddWithValue("@limit", limit);
        
        if (!string.IsNullOrEmpty(clientId))
        {
            command.Parameters.AddWithValue("@clientId", clientId);
        }

        await using var reader = await command.ExecuteReaderAsync(ct);
        
        while (await reader.ReadAsync(ct))
        {
            results.Add(new ChunkSearchResult
            {
                ChunkId = reader.GetString(0),
                DocumentId = reader.GetString(1),
                ClientId = reader.IsDBNull(2) ? null : reader.GetString(2),
                Text = reader.GetString(3),
                Heading = reader.IsDBNull(4) ? null : reader.GetString(4),
                ChunkType = reader.GetString(5),
                Rank = reader.GetDouble(6)
            });
        }

        _logger.LogInformation("Found {Count} chunks for query: {Query}", results.Count, processedQuery);

        return results;
    }

    /// <summary>
    /// Search chunks using semantic similarity (vector search).
    /// </summary>
    public async Task<List<ChunkSearchResult>> SearchChunksSemanticAsync(
        Vector queryEmbedding,
        string? clientId,
        int limit,
        CancellationToken ct = default)
    {
        _logger.LogInformation("Semantic search for chunks, ClientId: {ClientId}", clientId);

        var sql = @"
            SELECT 
                chunk_id,
                document_id,
                client_id,
                text,
                heading,
                chunk_type,
                1 - (embedding <=> @embedding::vector) as similarity
            FROM chunks
            WHERE embedding IS NOT NULL
            " + (string.IsNullOrEmpty(clientId) ? "" : "AND client_id = @clientId") + @"
            ORDER BY embedding <=> @embedding::vector
            LIMIT @limit";

        var results = new List<ChunkSearchResult>();

        await using var connection = (NpgsqlConnection)_context.Database.GetDbConnection();
        await connection.OpenAsync(ct);

        await using var command = new NpgsqlCommand(sql, connection);
        command.Parameters.AddWithValue("@embedding", queryEmbedding.ToArray());
        command.Parameters.AddWithValue("@limit", limit);

        if (!string.IsNullOrEmpty(clientId))
        {
            command.Parameters.AddWithValue("@clientId", clientId);
        }

        await using var reader = await command.ExecuteReaderAsync(ct);

        while (await reader.ReadAsync(ct))
        {
            results.Add(new ChunkSearchResult
            {
                ChunkId = reader.GetString(0),
                DocumentId = reader.GetString(1),
                ClientId = reader.IsDBNull(2) ? null : reader.GetString(2),
                Text = reader.GetString(3),
                Heading = reader.IsDBNull(4) ? null : reader.GetString(4),
                ChunkType = reader.GetString(5),
                Rank = reader.GetDouble(6)
            });
        }

        _logger.LogInformation("Semantic search found {Count} chunks", results.Count);

        return results;
    }

    /// <summary>
    /// Hybrid search combining fulltext and semantic search with RRF fusion.
    /// </summary>
    public async Task<List<ChunkSearchResult>> SearchChunksHybridAsync(
        string query,
        Vector? queryEmbedding,
        string? clientId,
        int limit,
        CancellationToken ct = default)
    {
        _logger.LogInformation("Hybrid search for query: {Query}, ClientId: {ClientId}", query, clientId);

        // If no embedding, fall back to fulltext only
        if (queryEmbedding == null)
        {
            return await SearchChunksAsync(query, clientId, limit, ct);
        }

        var processedQuery = PreprocessQuery(query);

        // Hybrid search using Reciprocal Rank Fusion (RRF)
        // RRF combines rankings from different search methods
        var sql = @"
            WITH fulltext_results AS (
                SELECT 
                    chunk_id,
                    document_id,
                    client_id,
                    text,
                    heading,
                    chunk_type,
                    ROW_NUMBER() OVER (ORDER BY ts_rank(to_tsvector('russian', text), plainto_tsquery('russian', @query)) DESC) as ft_rank
                FROM chunks
                WHERE to_tsvector('russian', text) @@ plainto_tsquery('russian', @query)
                " + (string.IsNullOrEmpty(clientId) ? "" : "AND client_id = @clientId") + @"
                LIMIT 50
            ),
            semantic_results AS (
                SELECT 
                    chunk_id,
                    document_id,
                    client_id,
                    text,
                    heading,
                    chunk_type,
                    ROW_NUMBER() OVER (ORDER BY embedding <=> @embedding::vector) as sem_rank
                FROM chunks
                WHERE embedding IS NOT NULL
                " + (string.IsNullOrEmpty(clientId) ? "" : "AND client_id = @clientId") + @"
                LIMIT 50
            ),
            combined AS (
                SELECT 
                    COALESCE(f.chunk_id, s.chunk_id) as chunk_id,
                    COALESCE(f.document_id, s.document_id) as document_id,
                    COALESCE(f.client_id, s.client_id) as client_id,
                    COALESCE(f.text, s.text) as text,
                    COALESCE(f.heading, s.heading) as heading,
                    COALESCE(f.chunk_type, s.chunk_type) as chunk_type,
                    -- RRF formula: 1/(k + rank) where k=60 is a common constant
                    COALESCE(1.0 / (60 + f.ft_rank), 0) + COALESCE(1.0 / (60 + s.sem_rank), 0) as rrf_score
                FROM fulltext_results f
                FULL OUTER JOIN semantic_results s ON f.chunk_id = s.chunk_id
            )
            SELECT 
                chunk_id,
                document_id,
                client_id,
                text,
                heading,
                chunk_type,
                rrf_score as rank
            FROM combined
            ORDER BY rrf_score DESC
            LIMIT @limit";

        var results = new List<ChunkSearchResult>();

        await using var connection = (NpgsqlConnection)_context.Database.GetDbConnection();
        await connection.OpenAsync(ct);

        await using var command = new NpgsqlCommand(sql, connection);
        command.Parameters.AddWithValue("@query", processedQuery);
        command.Parameters.AddWithValue("@embedding", queryEmbedding.ToArray());
        command.Parameters.AddWithValue("@limit", limit);

        if (!string.IsNullOrEmpty(clientId))
        {
            command.Parameters.AddWithValue("@clientId", clientId);
        }

        await using var reader = await command.ExecuteReaderAsync(ct);

        while (await reader.ReadAsync(ct))
        {
            results.Add(new ChunkSearchResult
            {
                ChunkId = reader.GetString(0),
                DocumentId = reader.GetString(1),
                ClientId = reader.IsDBNull(2) ? null : reader.GetString(2),
                Text = reader.GetString(3),
                Heading = reader.IsDBNull(4) ? null : reader.GetString(4),
                ChunkType = reader.GetString(5),
                Rank = reader.GetDouble(6)
            });
        }

        _logger.LogInformation("Hybrid search found {Count} chunks", results.Count);

        return results;
    }

    /// <summary>
    /// Preprocess query for fulltext search.
    /// </summary>
    private static string PreprocessQuery(string query)
    {
        // Remove special characters that might break tsquery
        return query
            .Replace("'", " ")
            .Replace("\"", " ")
            .Replace("(", " ")
            .Replace(")", " ")
            .Replace(":", " ")
            .Replace("&", " ")
            .Replace("|", " ")
            .Replace("!", " ")
            .Trim();
    }
}
