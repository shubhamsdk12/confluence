from neo4j import GraphDatabase
from app.config import settings
from app.utils.logger import db_logger
from app.ir.models import ClaimIR
from datetime import datetime


class GraphStore:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(GraphStore, cls).__new__(cls)
            cls._instance.driver = None
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

    def connect(self) -> bool:
        """Connect to Neo4j driver and ensure vector index is created."""
        if self.driver is not None:
            return True
        try:
            db_logger.info(f"Connecting to Neo4j at {settings.neo4j_uri}...")
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            # Verify connectivity
            self.driver.verify_connectivity()
            db_logger.info("Neo4j driver connected successfully.")
            self.create_vector_index()
            return True
        except Exception as e:
            db_logger.warning(
                f"Could not connect to Neo4j at {settings.neo4j_uri}: {e}"
            )
            self.driver = None
            return False

    def create_vector_index(self):
        """Create native Neo4j vector index for BusinessRule embeddings."""
        if not self.driver:
            return
        # Neo4j 5.x native vector index creation query
        query = """
        CREATE VECTOR INDEX compliance_rules_index IF NOT EXISTS
        FOR (r:BusinessRule) ON (r.embedding)
        OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}
        """
        try:
            with self.driver.session() as session:
                session.run(query)
                db_logger.info("Neo4j vector index 'compliance_rules_index' verified.")
        except Exception as e:
            db_logger.warning(f"Could not create Neo4j vector index: {e}")

    def close(self):
        if self.driver:
            self.driver.close()
            self.driver = None
            db_logger.info("Neo4j driver closed.")

    def create_claim_graph(self, ir: ClaimIR):
        """Create claim nodes and relationships in Neo4j."""
        if not self.driver and not self.connect():
            db_logger.warning("Neo4j not connected. Skipping create_claim_graph.")
            return

        query = """
        MERGE (pat:Patient {id: $patient_id})
        SET pat.name = $patient_name, 
            pat.dob = $patient_dob, 
            pat.member_id = $patient_member_id

        MERGE (prov:Provider {npi: $provider_npi})
        SET prov.name = $provider_name, 
            prov.taxonomy_code = $provider_taxonomy

        MERGE (c:Claim {claim_id: $claim_id})
        SET c.service_date = $service_date, 
            c.total_charge = $total_charge

        MERGE (pat)-[:SUBMITTED]->(c)
        MERGE (c)-[:BILLED_BY]->(prov)
        """

        try:
            with self.driver.session() as session:
                session.run(
                    query,
                    patient_id=ir.patient.id or "UNKNOWN",
                    patient_name=ir.patient.name or "UNKNOWN",
                    patient_dob=ir.patient.dob,
                    patient_member_id=ir.patient.member_id,
                    provider_npi=ir.provider.npi or "UNKNOWN",
                    provider_name=ir.provider.name or "UNKNOWN",
                    provider_taxonomy=ir.provider.taxonomy_code,
                    claim_id=ir.claim_id or "UNKNOWN",
                    service_date=ir.service_date or "",
                    total_charge=ir.total_charge,
                )

                # Create diagnosis relationships
                for code in ir.diagnosis_codes:
                    diag_query = """
                    MATCH (c:Claim {claim_id: $claim_id})
                    MERGE (d:DiagnosisCode {code: $code})
                    MERGE (c)-[:HAS_DIAGNOSIS {code: $code}]->(d)
                    """
                    session.run(diag_query, claim_id=ir.claim_id, code=code)

                # Create procedure relationships
                for code in ir.procedure_codes:
                    proc_query = """
                    MATCH (c:Claim {claim_id: $claim_id})
                    MERGE (p:ProcedureCode {code: $code})
                    MERGE (c)-[:HAS_PROCEDURE {code: $code}]->(p)
                    """
                    session.run(proc_query, claim_id=ir.claim_id, code=code)

                db_logger.info(
                    f"Successfully created graph nodes for claim {ir.claim_id}"
                )
        except Exception as e:
            db_logger.error(f"Failed to create claim graph in Neo4j: {e}")

    def link_claim_violation(self, claim_id: str, rule_id: str):
        """Link claim node to violated BusinessRule node in Neo4j."""
        if not self.driver and not self.connect():
            return
        query = """
        MATCH (c:Claim {claim_id: $claim_id})
        MATCH (r:BusinessRule {rule_id: $rule_id})
        MERGE (c)-[:VIOLATES]->(r)
        """
        try:
            with self.driver.session() as session:
                session.run(query, claim_id=claim_id, rule_id=rule_id)
        except Exception as e:
            db_logger.error(f"Failed to link claim violation: {e}")

    def query_vector_index(self, embedding: list[float], top_k: int = 3) -> list[dict]:
        """Query native Neo4j vector index compliance_rules_index."""
        if not self.driver and not self.connect():
            return []
        
        query = """
        CALL db.index.vector.queryNodes('compliance_rules_index', $top_k, $embedding)
        YIELD node, score
        RETURN node.rule_id as rule_id,
               node.name as name,
               node.description as description,
               node.severity as severity,
               node.industry as industry,
               score
        """
        results = []
        try:
            with self.driver.session() as session:
                res = session.run(query, embedding=embedding, top_k=top_k)
                for record in res:
                    results.append({
                        "rule_id": record["rule_id"],
                        "name": record["name"],
                        "description": record["description"],
                        "severity": record["severity"],
                        "industry": record["industry"],
                        "score": record["score"]
                    })
        except Exception as e:
            db_logger.error(f"Failed to query Neo4j vector index: {e}")
        return results

    def get_rule_relations(self, rule_id: str) -> dict:
        """Fetch Regulation and HistoricalFixes connected to a BusinessRule."""
        if not self.driver and not self.connect():
            return {"regulations": [], "historical_fixes": []}
        
        reg_query = """
        MATCH (r:BusinessRule {rule_id: $rule_id})-[:DEFINED_BY]->(reg:Regulation)
        RETURN reg.name as name, reg.standard as standard, reg.version as version
        """
        
        fix_query = """
        MATCH (r:BusinessRule {rule_id: $rule_id})-[:HAS_FIX]->(f:HistoricalFix)
        RETURN f.fix_id as fix_id, f.original_value as original_value, f.approved_fix as approved_fix
        """
        
        regulations = []
        historical_fixes = []
        try:
            with self.driver.session() as session:
                regs = session.run(reg_query, rule_id=rule_id)
                for record in regs:
                    regulations.append({
                        "name": record["name"],
                        "standard": record["standard"],
                        "version": record["version"]
                    })
                
                fixes = session.run(fix_query, rule_id=rule_id)
                for record in fixes:
                    historical_fixes.append({
                        "fix_id": record["fix_id"],
                        "original_value": record["original_value"],
                        "approved_fix": record["approved_fix"]
                    })
        except Exception as e:
            db_logger.error(f"Failed to fetch rule relationships for {rule_id}: {e}")
            
        return {"regulations": regulations, "historical_fixes": historical_fixes}

    def validate_duplicate_claim(self, claim_id: str) -> dict:
        """Check if claim_id is duplicated in the DB."""
        if not self.driver and not self.connect():
            return {
                "passed": True,
                "detail": "Neo4j offline; duplicate check skipped.",
            }

        query = """
        MATCH (c:Claim {claim_id: $claim_id})
        RETURN count(c) as count
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, claim_id=claim_id)
                record = result.single()
                count = record["count"] if record else 0
                if count > 1:
                    return {
                        "passed": False,
                        "detail": f"Duplicate claim detected. The claim ID '{claim_id}' has been submitted {count} times.",
                    }
                return {
                    "passed": True,
                    "detail": f"No duplicates found for claim ID '{claim_id}'.",
                }
        except Exception as e:
            db_logger.error(f"Error validating duplicate claim: {e}")
            return {
                "passed": True,
                "detail": f"Error running duplicate validation query: {e}",
            }

    def validate_provider_npi(self, npi: str) -> dict:
        """Check provider NPI is exactly 10 digits using regex."""
        if not self.driver and not self.connect():
            is_valid = npi.isdigit() and len(npi) == 10
            if not is_valid:
                return {
                    "passed": False,
                    "detail": f"Provider NPI '{npi}' is invalid (Python validation). Must be a 10-digit numeric string.",
                }
            return {
                "passed": True,
                "detail": f"Provider NPI '{npi}' is valid (Python validation).",
            }

        query = """
        RETURN $npi =~ '^[0-9]{10}$' as isValid
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, npi=npi)
                record = result.single()
                is_valid = record["isValid"] if record else False
                if not is_valid:
                    return {
                        "passed": False,
                        "detail": f"Provider NPI '{npi}' is invalid. NPI must be exactly a 10-digit numeric string.",
                    }
                return {
                    "passed": True,
                    "detail": f"Provider NPI '{npi}' is valid (10-digit numeric string).",
                }
        except Exception as e:
            db_logger.error(f"Error validating NPI in Neo4j: {e}")
            is_valid = npi.isdigit() and len(npi) == 10
            if not is_valid:
                return {
                    "passed": False,
                    "detail": f"Provider NPI '{npi}' is invalid (fallback validation).",
                }
            return {
                "passed": True,
                "detail": f"Provider NPI '{npi}' is valid (fallback validation).",
            }

    def validate_service_date(self, claim_id: str, service_date_val: str = None) -> dict:
        """Flag claims with future service dates."""
        if not self.driver and not self.connect():
            if not service_date_val:
                return {
                    "passed": True,
                    "detail": "Neo4j offline; service date check skipped.",
                }
            # Fallback to Python date check
            service_date = None
            for fmt in ("%Y%m%d", "%Y-%m-%d"):
                try:
                    service_date = datetime.strptime(service_date_val, fmt).date()
                    break
                except ValueError:
                    continue

            if service_date is None:
                return {
                    "passed": False,
                    "detail": f"Service date '{service_date_val}' is invalid or could not be parsed.",
                }

            today = datetime.now().date()
            if service_date > today:
                return {
                    "passed": False,
                    "detail": f"Service date '{service_date_val}' is in the future (Python validation). Today's date is {today.strftime('%Y-%m-%d')}.",
                }
            return {
                "passed": True,
                "detail": f"Service date '{service_date_val}' is valid (Python validation).",
            }

        query = """
        MATCH (c:Claim {claim_id: $claim_id})
        RETURN c.service_date as service_date
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, claim_id=claim_id)
                records = list(result)
                if not records:
                    return {"passed": True, "detail": "Claim not found in graph."}

                service_date_str = records[-1]["service_date"]
                if not service_date_str:
                    return {"passed": False, "detail": "Service date is missing."}

                service_date = None
                for fmt in ("%Y%m%d", "%Y-%m-%d"):
                    try:
                        service_date = datetime.strptime(
                            service_date_str, fmt
                        ).date()
                        break
                    except ValueError:
                        continue

                if service_date is None:
                    return {
                        "passed": False,
                        "detail": f"Service date '{service_date_str}' is invalid or could not be parsed.",
                    }

                today = datetime.now().date()
                if service_date > today:
                    return {
                        "passed": False,
                        "detail": f"Service date '{service_date_str}' is in the future. Today's date is {today.strftime('%Y-%m-%d')}.",
                    }
                return {
                    "passed": True,
                    "detail": f"Service date '{service_date_str}' is valid.",
                }
        except Exception as e:
            db_logger.error(f"Error validating service date: {e}")
            return {
                "passed": True,
                "detail": f"Error running service date validation query: {e}",
            }


graph_store = GraphStore()
