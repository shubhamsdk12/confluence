import uuid
from sentence_transformers import SentenceTransformer
from app.knowledge.graph_store import graph_store
from app.utils.logger import db_logger

# Define 16 compliance rules across industries
RULES_DATA = [
    # HEALTHCARE (HIPAA / X12)
    {
        "rule_id": "RULE_HIPAA_CLM",
        "name": "Missing CLM Segment",
        "description": "HIPAA X12 837P: CLM segment is mandatory. Missing CLM constitutes a fatal structural error.",
        "industry": "healthcare",
        "severity": "critical",
        "regulation": {
            "reg_id": "REG_HIPAA_837P",
            "name": "HIPAA 837 Professional Claim Standards",
            "standard": "HIPAA",
            "version": "5010"
        },
        "fix": {
            "original_value": "",
            "approved_fix": "Add CLM segment"
        }
    },
    {
        "rule_id": "RULE_HIPAA_NPI",
        "name": "Invalid NPI Format",
        "description": "NPI (National Provider Identifier) must be a 10-digit numeric string. Invalid NPI causes claim rejection.",
        "industry": "healthcare",
        "severity": "critical",
        "regulation": {
            "reg_id": "REG_HIPAA_NPI",
            "name": "NPI Standard Rule",
            "standard": "HIPAA",
            "version": "NPPES-v1"
        },
        "fix": {
            "original_value": "12345",
            "approved_fix": "1234567890"
        }
    },
    {
        "rule_id": "RULE_HIPAA_DIAG",
        "name": "Missing Diagnosis Codes",
        "description": "ICD-10 diagnosis codes must be present on every professional claim. Minimum one HI segment required.",
        "industry": "healthcare",
        "severity": "critical",
        "regulation": {
            "reg_id": "REG_HIPAA_ICD10",
            "name": "ICD-10 Code Set Mandate",
            "standard": "HIPAA",
            "version": "ICD-10-CM"
        },
        "fix": {
            "original_value": "",
            "approved_fix": "Add diagnosis code 'M54.5'"
        }
    },
    {
        "rule_id": "RULE_HIPAA_PROC",
        "name": "Missing Procedure Codes",
        "description": "Procedure code must be a valid CPT-4 or HCPCS Level II code. Minimum one SV1 segment required.",
        "industry": "healthcare",
        "severity": "critical",
        "regulation": {
            "reg_id": "REG_HIPAA_CPT",
            "name": "CPT/HCPCS Procedure Coding Guidelines",
            "standard": "HIPAA",
            "version": "CPT-4"
        },
        "fix": {
            "original_value": "",
            "approved_fix": "Add procedure code '99213'"
        }
    },
    {
        "rule_id": "RULE_HIPAA_DATE",
        "name": "Future Service Date",
        "description": "Future service date is prohibited. Service date must be on or before the upload date.",
        "industry": "healthcare",
        "severity": "critical",
        "regulation": {
            "reg_id": "REG_HIPAA_TEMPORAL",
            "name": "Temporal Billing Guidelines",
            "standard": "HIPAA",
            "version": "1.0"
        },
        "fix": {
            "original_value": "2030-12-31",
            "approved_fix": "2026-06-26"
        }
    },
    {
        "rule_id": "RULE_HIPAA_DUP",
        "name": "Duplicate Claim ID",
        "description": "Duplicate claim validation. A claim ID cannot be submitted multiple times.",
        "industry": "healthcare",
        "severity": "critical",
        "regulation": {
            "reg_id": "REG_HIPAA_DUP",
            "name": "Duplicate Submission Validation",
            "standard": "HIPAA",
            "version": "1.0"
        },
        "fix": {
            "original_value": "CLM001",
            "approved_fix": "CLM001-REV1"
        }
    },
    {
        "rule_id": "RULE_HIPAA_PATIENT",
        "name": "Missing Patient ID",
        "description": "Patient identifier is mandatory (NM1*QC segment).",
        "industry": "healthcare",
        "severity": "critical",
        "regulation": {
            "reg_id": "REG_HIPAA_837P",
            "name": "HIPAA 837 Professional Claim Standards",
            "standard": "HIPAA",
            "version": "5010"
        },
        "fix": {
            "original_value": "",
            "approved_fix": "Add patient details"
        }
    },

    # BANKING (ISO 20022)
    {
        "rule_id": "RULE_ISO20022_IBAN",
        "name": "Invalid IBAN Format",
        "description": "IBAN (International Bank Account Number) must match the country-specific length and ISO 7064 checksum format.",
        "industry": "banking",
        "severity": "critical",
        "regulation": {
            "reg_id": "REG_ISO20022",
            "name": "ISO 20022 Financial Messaging",
            "standard": "ISO20022",
            "version": "2013"
        },
        "fix": {
            "original_value": "GB82WEST12345",
            "approved_fix": "GB82WEST12345678901234"
        }
    },
    {
        "rule_id": "RULE_ISO20022_BIC",
        "name": "Invalid BIC Code",
        "description": "BIC (Bank Identifier Code) must be exactly 8 or 11 alphanumeric characters.",
        "industry": "banking",
        "severity": "critical",
        "regulation": {
            "reg_id": "REG_ISO9362",
            "name": "ISO 9362 BIC Regulation",
            "standard": "ISO9362",
            "version": "2014"
        },
        "fix": {
            "original_value": "WEST12",
            "approved_fix": "WESTGB2LXXX"
        }
    },
    {
        "rule_id": "RULE_ISO20022_CURR",
        "name": "Invalid Currency Code",
        "description": "Transaction currency must be a valid ISO 4217 three-letter alphabetic currency code (e.g. USD, EUR, INR).",
        "industry": "banking",
        "severity": "critical",
        "regulation": {
            "reg_id": "REG_ISO4217",
            "name": "ISO 4217 Currency Standards",
            "standard": "ISO4217",
            "version": "2015"
        },
        "fix": {
            "original_value": "US",
            "approved_fix": "USD"
        }
    },
    {
        "rule_id": "RULE_ISO20022_AMT",
        "name": "Negative Amount Check",
        "description": "Transaction amount must be positive and non-zero.",
        "industry": "banking",
        "severity": "critical",
        "regulation": {
            "reg_id": "REG_ISO20022",
            "name": "ISO 20022 Financial Messaging",
            "standard": "ISO20022",
            "version": "2013"
        },
        "fix": {
            "original_value": "-150.00",
            "approved_fix": "150.00"
        }
    },

    # TAXATION / INSURANCE / OTHERS
    {
        "rule_id": "RULE_GST_GSTIN",
        "name": "Invalid GSTIN format",
        "description": "GSTIN (Goods and Services Tax Identification Number) must be a 15-digit alphanumeric string.",
        "industry": "insurance",
        "severity": "critical",
        "regulation": {
            "reg_id": "REG_GST_ACT",
            "name": "GST Act Section 22",
            "standard": "GST",
            "version": "2017"
        },
        "fix": {
            "original_value": "22ABCDE1234",
            "approved_fix": "22ABCDE1234F1Z5"
        }
    },
    {
        "rule_id": "RULE_GST_STATE",
        "name": "GST State Code Mismatch",
        "description": "Place of Supply (POS) must match the State Code prefix of the GSTIN for CGST/SGST vs IGST calculation.",
        "industry": "insurance",
        "severity": "warning",
        "regulation": {
            "reg_id": "REG_GST_ACT",
            "name": "GST Act Section 22",
            "standard": "GST",
            "version": "2017"
        },
        "fix": {
            "original_value": "POS State: MH, GSTIN: 22(CG)",
            "approved_fix": "Match POS to GSTIN State"
        }
    },
    {
        "rule_id": "RULE_X12_ISA",
        "name": "Invalid ISA Length",
        "description": "ISA segment must be exactly 106 characters long and have appropriate delimiters.",
        "industry": "healthcare",
        "severity": "critical",
        "regulation": {
            "reg_id": "REG_X12_HEADER",
            "name": "X12 EDI Header Standards",
            "standard": "X12",
            "version": "004010"
        },
        "fix": {
            "original_value": "Short ISA Segment",
            "approved_fix": "Pad ISA Segment to 106 characters"
        }
    },
    {
        "rule_id": "RULE_X12_GS",
        "name": "Missing GS Segment",
        "description": "GS functional group header segment is mandatory.",
        "industry": "healthcare",
        "severity": "critical",
        "regulation": {
            "reg_id": "REG_X12_HEADER",
            "name": "X12 Functional Group Standards",
            "standard": "X12",
            "version": "004010"
        },
        "fix": {
            "original_value": "",
            "approved_fix": "Add GS segment"
        }
    },
    {
        "rule_id": "RULE_X12_GE",
        "name": "GS/GE Count Mismatch",
        "description": "GE functional group trailer segment count must match GS functional control number.",
        "industry": "healthcare",
        "severity": "warning",
        "regulation": {
            "reg_id": "REG_X12_HEADER",
            "name": "X12 Functional Group Standards",
            "standard": "X12",
            "version": "004010"
        },
        "fix": {
            "original_value": "GS=1, GE=2",
            "approved_fix": "GS=1, GE=1"
        }
    }
]


def seed_neo4j_database():
    """Generate rule embeddings and seed BusinessRules, Regulations, and HistoricalFixes in Neo4j."""
    if not graph_store.connect():
        db_logger.error("Could not connect to Neo4j database. Seeding aborted.")
        return

    db_logger.info("Starting Neo4j GraphRAG database seeding...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # Wipe existing compliance rules to ensure fresh seed
    clear_query = """
    MATCH (r:BusinessRule) DETACH DELETE r;
    """
    try:
        with graph_store.driver.session() as session:
            session.run("MATCH (r:BusinessRule) DETACH DELETE r")
            session.run("MATCH (reg:Regulation) DETACH DELETE reg")
            session.run("MATCH (f:HistoricalFix) DETACH DELETE f")
            db_logger.info("Cleared previous BusinessRule, Regulation, and HistoricalFix nodes.")
    except Exception as e:
        db_logger.warning(f"Error during node cleanup: {e}")

    # Seed loop
    for rule in RULES_DATA:
        # Create embedding of the rule description
        embedding_text = f"{rule['name']}: {rule['description']}"
        embedding = model.encode(embedding_text).tolist()

        query = """
        // 1. Create BusinessRule
        MERGE (br:BusinessRule {rule_id: $rule_id})
        SET br.name = $name,
            br.description = $description,
            br.industry = $industry,
            br.severity = $severity,
            br.embedding = $embedding

        // 2. Create Regulation and link
        MERGE (reg:Regulation {reg_id: $reg_id})
        SET reg.name = $reg_name,
            reg.standard = $reg_standard,
            reg.version = $reg_version
        MERGE (br)-[:DEFINED_BY]->(reg)

        // 3. Create HistoricalFix and link
        MERGE (fix:HistoricalFix {fix_id: $fix_id})
        SET fix.original_value = $original_value,
            fix.approved_fix = $approved_fix,
            fix.industry = $industry,
            fix.field = $field
        MERGE (br)-[:HAS_FIX]->(fix)
        """
        
        # Determine unique fix ID and field name
        fix_id = f"FIX_{rule['rule_id']}"
        field_map = {
            "RULE_HIPAA_CLM": "claim_id",
            "RULE_HIPAA_NPI": "provider.npi",
            "RULE_HIPAA_DIAG": "diagnosis_codes",
            "RULE_HIPAA_PROC": "procedure_codes",
            "RULE_HIPAA_DATE": "service_date",
            "RULE_HIPAA_DUP": "claim_id",
            "RULE_HIPAA_PATIENT": "patient.id",
            "RULE_ISO20022_IBAN": "iban",
            "RULE_ISO20022_BIC": "bic",
            "RULE_ISO20022_CURR": "currency",
            "RULE_ISO20022_AMT": "amount",
            "RULE_GST_GSTIN": "gstin",
            "RULE_GST_STATE": "place_of_supply",
            "RULE_X12_ISA": "isa_segment",
            "RULE_X12_GS": "gs_segment",
            "RULE_X12_GE": "ge_segment"
        }
        field_name = field_map.get(rule["rule_id"], "document")

        try:
            with graph_store.driver.session() as session:
                session.run(
                    query,
                    rule_id=rule["rule_id"],
                    name=rule["name"],
                    description=rule["description"],
                    industry=rule["industry"],
                    severity=rule["severity"],
                    embedding=embedding,
                    reg_id=rule["regulation"]["reg_id"],
                    reg_name=rule["regulation"]["name"],
                    reg_standard=rule["regulation"]["standard"],
                    reg_version=rule["regulation"]["version"],
                    fix_id=fix_id,
                    original_value=rule["fix"]["original_value"],
                    approved_fix=rule["fix"]["approved_fix"],
                    field=field_name
                )
            db_logger.info(f"Seeded rule: {rule['rule_id']} ({rule['name']})")
        except Exception as e:
            db_logger.error(f"Failed to seed rule {rule['rule_id']}: {e}")

    db_logger.info("Successfully seeded 16 compliance rules into Neo4j database.")


if __name__ == "__main__":
    seed_neo4j_database()
