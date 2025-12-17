using System.ComponentModel.DataAnnotations;
using System.ComponentModel.DataAnnotations.Schema;

namespace DocRag.Models;

/// <summary>
/// Represents a document with OCR-extracted fulltext.
/// </summary>
[Table("documents")]
public class Document
{
    [Key]
    [Column("id")]
    public int Id { get; set; }

    [Required]
    [Column("document_id")]
    [MaxLength(255)]
    public string DocumentId { get; set; } = string.Empty;

    [Column("client_id")]
    [MaxLength(255)]
    public string? ClientId { get; set; }

    [Column("filename")]
    [MaxLength(500)]
    public string? Filename { get; set; }

    [Column("fulltext")]
    public string? Fulltext { get; set; }

    [Column("metadata", TypeName = "jsonb")]
    public string? Metadata { get; set; }

    [Column("created_at")]
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    [Column("updated_at")]
    public DateTime? UpdatedAt { get; set; }

    // Navigation property
    public virtual ICollection<Chunk> Chunks { get; set; } = new List<Chunk>();
}
