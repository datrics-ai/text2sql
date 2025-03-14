import numpy as np
import json
from chromadb import QueryResult
from chromadb.config import Settings
from chromadb.utils.embedding_functions.openai_embedding_function import (
    OpenAIEmbeddingFunction,
)
from t2sql.utils import deterministic_uuid
import pandas as pd
import chromadb
import asyncio
from t2sql.vectordb.base import VectorStore


# TODO move to proper async
class ChromaDB(VectorStore):
    def __init__(self, config: dict):
        super().__init__(config)

        path = config.get("db_path", ".")
        self.embedding_function = OpenAIEmbeddingFunction(config.get("open_ai_key"))

        curr_client = config.get("client", "persistent")
        collection_metadata = config.get("collection_metadata", {})
        collection_metadata["db_path"] = path

        self.n_results_sql = config.get("n_results_sql", config.get("n_results", 10))
        self.n_results_documentation = config.get(
            "n_results_documentation", config.get("n_results", 10)
        )
        self.n_results_ddl = config.get("n_results_ddl", config.get("n_results", 10))

        if curr_client == "persistent":
            self.chroma_client = chromadb.PersistentClient(
                path=path, settings=Settings(anonymized_telemetry=False)
            )
        elif curr_client == "in-memory":
            self.chroma_client = chromadb.EphemeralClient(
                settings=Settings(anonymized_telemetry=False)
            )
        elif isinstance(curr_client, chromadb.api.client.Client):
            # allow providing client directly
            self.chroma_client = curr_client
        else:
            raise ValueError(f"Unsupported client was set in config: {curr_client}")

        self.documentation_collection = self.chroma_client.get_or_create_collection(
            name="documentation",
            embedding_function=self.embedding_function,
            metadata=collection_metadata,
        )
        self.ddl_collection = self.chroma_client.get_or_create_collection(
            name="ddl",
            embedding_function=self.embedding_function,
            metadata=collection_metadata,
        )
        self.sql_collection = self.chroma_client.get_or_create_collection(
            name="sql",
            embedding_function=self.embedding_function,
            metadata=collection_metadata,
        )
        self.questions_tables_collection = self.chroma_client.get_or_create_collection(
            name="question_tables",
            embedding_function=self.embedding_function,
            metadata=collection_metadata,
        )

    async def generate_embedding(self, data: str, **kwargs) -> list[float]:
        embedding = await asyncio.to_thread(self.embedding_function, [data])
        if len(embedding) == 1:
            return embedding[0]
        return embedding

    async def add_documentation(
        self,
        documentation: str,
        question: str = None,
        metadatas=None,
        add_name=None,
        **kwargs,
    ) -> str:
        id = deterministic_uuid(f"{add_name}{question}{documentation}") + "-doc"

        if question is not None:
            documents = json.dumps(
                {"question": question, "documentation": documentation}
            )
            await asyncio.to_thread(
                self.documentation_collection.add,
                documents=documents,
                embeddings=await self.generate_embedding(question),
                ids=id,
                metadatas=metadatas,
            )
        else:
            documents = json.dumps({"question": None, "documentation": documentation})
            await asyncio.to_thread(
                self.documentation_collection.add,
                documents=documents,
                embeddings=await self.generate_embedding(documentation),
                ids=id,
                metadatas=metadatas,
            )
        return id

    async def add_question_sql(
        self, question: str, sql: str, metadatas=None, **kwargs
    ) -> str:
        question_sql_json = json.dumps(
            {
                "question": question,
                "sql": sql,
            },
            ensure_ascii=False,
        )
        id = deterministic_uuid(question_sql_json) + "-sql"
        await asyncio.to_thread(
            self.sql_collection.add,
            documents=question_sql_json,
            embeddings=await self.generate_embedding(question),
            ids=id,
            metadatas=metadatas,
        )

        return id

    async def add_ddl(self, ddl: str, **kwargs) -> str:
        id = deterministic_uuid(ddl) + "-ddl"
        await asyncio.to_thread(
            self.ddl_collection.add,
            documents=ddl,
            embeddings=await self.generate_embedding(ddl),
            ids=id,
        )
        return id

    async def add_question_tables_relation(
        self, id: str, question_doc_json: str, question: str
    ):
        await asyncio.to_thread(
            self.questions_tables_collection.add,
            documents=question_doc_json,
            embeddings=await self.generate_embedding(question),
            ids=id,
        )

    async def get_all_documentation(self) -> list:
        query_result = await asyncio.to_thread(self.documentation_collection.get)
        result = {}
        for i in range(len(query_result["metadatas"])):
            document_name = query_result["metadatas"][i]["document_name"]
            document_full = query_result["metadatas"][i].get("description_full")
            document_id = query_result["ids"][i]
            if document_full is None:
                continue

            if document_name not in result:
                result[document_name] = {
                    "name": document_name,
                    "document": document_full,
                    "ids": [document_id],
                }
            else:
                result[document_name]["ids"].append(document_id)

        return list(result.values())

    async def get_document_by_name(self, document_name: str) -> dict:
        query_result = await asyncio.to_thread(
            self.documentation_collection.get, where={"document_name": document_name}
        )
        return {
            "ids": query_result["ids"],
            "documents": query_result["documents"],
            "metadatas": query_result["metadatas"],
        }

    async def get_examples_by_question_name(self, question: str) -> dict:
        query_result = await asyncio.to_thread(
            self.sql_collection.get, where={"question": question}
        )
        return {
            "ids": query_result["ids"],
            "documents": query_result["documents"],
            "metadatas": query_result["metadatas"],
        }

    async def delete_documents_by_ids(self, ids: list[str]):
        await asyncio.to_thread(self.documentation_collection.delete, ids=ids)

    @staticmethod
    def extract_documents(query_results: QueryResult) -> list:
        documents = []
        if query_results is None:
            return documents

        if "documents" in query_results:
            documents = query_results["documents"]

            if len(documents) == 1 and isinstance(documents[0], list):
                try:
                    documents = [json.loads(doc) for doc in documents[0]]
                except Exception as e:
                    return documents[0]

        return documents

    def remove_collection(self, collection_name: str) -> bool:
        if collection_name == "sql":
            self.chroma_client.delete_collection(name="sql")
            self.sql_collection = self.chroma_client.get_or_create_collection(
                name="sql", embedding_function=self.embedding_function
            )
            return True
        elif collection_name == "ddl":
            self.chroma_client.delete_collection(name="ddl")
            self.ddl_collection = self.chroma_client.get_or_create_collection(
                name="ddl", embedding_function=self.embedding_function
            )
            return True
        elif collection_name == "documentation":
            self.chroma_client.delete_collection(name="documentation")
            self.documentation_collection = self.chroma_client.get_or_create_collection(
                name="documentation", embedding_function=self.embedding_function
            )
            return True
        elif collection_name == "question_tables":
            self.chroma_client.delete_collection(name="question_tables")
            self.questions_tables_collection = (
                self.chroma_client.get_or_create_collection(
                    name="question_tables", embedding_function=self.embedding_function
                )
            )
            return True
        return False

    async def remove_training_data(self, id: list[str]) -> bool:
        if len(id) == 0:
            return False

        if id[0].endswith("-sql"):
            await asyncio.to_thread(self.sql_collection.delete, ids=id)
            return True
        elif id[0].endswith("-ddl"):
            await asyncio.to_thread(self.ddl_collection.delete, ids=id)
            return True
        elif id[0].endswith("-doc"):
            await asyncio.to_thread(self.documentation_collection.delete, ids=id)
            return True
        elif id[0].endswith("qst-doc"):
            await asyncio.to_thread(self.questions_tables_collection.delete, ids=id)
            return True
        return False

    def get_training_data(self, **kwargs) -> pd.DataFrame:
        sql_data = self.sql_collection.get()

        df = pd.DataFrame()

        if sql_data is not None:
            # Extract the documents and ids
            documents = [json.loads(doc) for doc in sql_data["documents"]]
            ids = sql_data["ids"]

            # Create a DataFrame
            df_sql = pd.DataFrame(
                {
                    "id": ids,
                    "question": [doc["question"] for doc in documents],
                    "content": [doc["sql"] for doc in documents],
                }
            )

            df_sql["training_data_type"] = "sql"

            df = pd.concat([df, df_sql])

        ddl_data = self.ddl_collection.get()

        if ddl_data is not None:
            # Extract the documents and ids
            documents = [doc for doc in ddl_data["documents"]]
            ids = ddl_data["ids"]

            # Create a DataFrame
            df_ddl = pd.DataFrame(
                {
                    "id": ids,
                    "question": [None for doc in documents],
                    "content": [doc for doc in documents],
                }
            )

            df_ddl["training_data_type"] = "ddl"

            df = pd.concat([df, df_ddl])

        doc_data = self.documentation_collection.get()

        if doc_data is not None:
            # Extract the documents and ids
            documents = [doc for doc in doc_data["documents"]]
            ids = doc_data["ids"]

            # Create a DataFrame
            df_doc = pd.DataFrame(
                {
                    "id": ids,
                    "question": [None for doc in documents],
                    "content": [doc for doc in documents],
                }
            )

            df_doc["training_data_type"] = "documentation"

            df = pd.concat([df, df_doc])

        return df

    @staticmethod
    def filter_by_distance_score_sql(
        result: list,
        query_result: QueryResult,
        min_score: float,
        best_score: float,
        break_if_close: bool = False,
        indexes: list = None,
    ) -> tuple[list, bool, list]:
        if indexes is None:
            indexes = list(range(len(query_result["distances"][0])))

        distances = query_result["distances"][0]
        sorted_indices = np.argsort(distances)
        sorted_distances = distances[sorted_indices]

        filtered_results = []
        unique_tables = []
        has_best_example = False

        for idx, distance in zip(sorted_indices, sorted_distances):
            if idx not in indexes:
                continue

            if distance >= min_score:
                break

            # Extract and parse structure from metadata
            structure = json.loads(
                query_result["metadatas"][0][idx].get("structure", "{}")
            )

            # Add structure to result and append to filtered results
            result_with_structure = result[idx] | {"structure": structure}
            filtered_results.append(result_with_structure)

            # Update unique tables list
            tables_from_structure = structure.get("tables", [])
            unique_tables = list(set(unique_tables + tables_from_structure))

            # Check for best example
            if distance < best_score:
                has_best_example = True
                if break_if_close:
                    break

        return filtered_results, has_best_example, unique_tables

    async def get_related_sql(self, question: str) -> QueryResult:
        return await asyncio.to_thread(
            self.sql_collection.query,
            query_texts=[question],
            n_results=self.n_results_sql,
        )

    def get_related_ddl(self, question: str, **kwargs) -> list:
        return ChromaDB.extract_documents(
            self.ddl_collection.query(
                query_texts=[question],
                n_results=self.n_results_ddl,
            )
        )

    def get_related_documentation(self, question: str, **kwargs) -> list:
        return ChromaDB.extract_documents(
            self.documentation_collection.query(
                query_texts=[question],
                n_results=self.n_results_documentation,
            )
        )

    async def query_documentation(self, **kwargs) -> QueryResult:
        return await asyncio.to_thread(self.documentation_collection.query, **kwargs)

    async def return_table_docs(self, list_tables: list[str]):
        _tables = []
        _descr = []
        for t in list_tables:
            r = await asyncio.to_thread(
                self.documentation_collection.get,
                where={"$and": [{"category": "table_name"}, {"table": t}]},
            )
            r = r["metadatas"]
            if len(r) > 0:
                r = r[0]
                _tables.append(t)
                _descr.append(r["description_full"])
        docs_to_sql = "\n\n".join(_descr)
        return docs_to_sql, _tables

    async def get_domain_instructions(self) -> str:
        domain_insts = await asyncio.to_thread(self.questions_tables_collection.get)
        doc = "{}"
        for doc in domain_insts["documents"]:
            if json.loads(doc)["question"] == "EXTRACTED DOMAIN-SPECIFIC MAPPING":
                break
        domain_instr = json.loads(doc).get("tables", "")
        return domain_instr
