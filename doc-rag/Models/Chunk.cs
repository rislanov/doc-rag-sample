using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;
using Pgvector;

namespace DocRag.Models;

/// <summary>
/// Represents a semantic chunk of a document for RAG.
/// </summary>
[Table("chunks")]
public class Chunk
{
    [Key]
    [Column("id")]
    public int Id { get; set; }

    [Required]
    [Column("chunk_id")]
    [MaxLength(255)]
    public string ChunkId { get; set; } = string.Empty;

    [Required]
    [Column("document_id")]
    [MaxLength(255)]
    public string DocumentId { get; set; } = string.Empty;

    [Column("client_id")]
    [MaxLength(255)]
    public string? ClientId { get; set; }

    [Column("chunk_index")]
    public int ChunkIndex { get; set; }

    [Required]
    [Column("text")]
    public string Text { get; set; } = string.Empty;

    [Column("heading")]
    [MaxLength(500)]
    public string? Heading { get; set; }

    [Column("heading_level")]
    public int HeadingLevel { get; set; }

    [Column("chunk_type")]
    [MaxLength(50)]
    public string ChunkType { get; set; } = "general";

    [Column("token_count")]
    public int TokenCount { get; set; }

    [Column("embedding")]
    public Vector? Embedding { get; set; }

    [Column("created_at")]
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    [Column("updated_at")]
    public DateTime? UpdatedAt { get; set; }
}
