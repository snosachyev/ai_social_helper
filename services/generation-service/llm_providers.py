"""LLM Provider Abstraction Layer"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, AsyncGenerator
import openai
import tiktoken
from datetime import datetime
import json

from shared.models.base import GenerationRequest, RetrievalResult

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate_response(
        self,
        query: str,
        context: List[RetrievalResult],
        model_name: str = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stream: bool = False
    ) -> str | AsyncGenerator[str, None]:
        """Generate response based on query and context."""
        pass
    
    @abstractmethod
    async def count_tokens(self, text: str, model_name: str = None) -> int:
        """Count tokens in text."""
        pass
    
    @abstractmethod
    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get model information."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is healthy."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""
    
    def __init__(self, api_key: str, base_url: str = None):
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.default_model = "gpt-3.5-turbo"
        self.models = {
            "gpt-3.5-turbo": {
                "max_tokens": 4096,
                "cost_per_1k_input": 0.001,
                "cost_per_1k_output": 0.002
            },
            "gpt-4": {
                "max_tokens": 8192,
                "cost_per_1k_input": 0.03,
                "cost_per_1k_output": 0.06
            },
            "gpt-4-turbo": {
                "max_tokens": 128000,
                "cost_per_1k_input": 0.01,
                "cost_per_1k_output": 0.03
            }
        }
    
    async def generate_response(
        self,
        query: str,
        context: List[RetrievalResult],
        model_name: str = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stream: bool = False
    ) -> str | AsyncGenerator[str, None]:
        """Generate response using OpenAI API."""
        if model_name is None:
            model_name = self.default_model
        
        # Create prompt with context
        messages = self._create_messages(query, context)
        
        try:
            if stream:
                return await self._stream_response(
                    messages, model_name, max_tokens, temperature
                )
            else:
                response = await self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=False
                )
                
                return response.choices[0].message.content
                
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    async def _stream_response(
        self,
        messages: List[Dict],
        model_name: str,
        max_tokens: int,
        temperature: float
    ) -> AsyncGenerator[str, None]:
        """Stream response from OpenAI."""
        try:
            stream = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            raise
    
    def _create_messages(self, query: str, context: List[RetrievalResult]) -> List[Dict]:
        """Create messages for OpenAI chat completion."""
        context_text = "\n\n".join([
            f"Context {i+1}: {result.text}"
            for i, result in enumerate(context[:5])  # Limit context to top 5
        ])
        
        system_prompt = """You are a helpful AI assistant. Based on the provided context, 
        please answer the user's question accurately and concisely. If the context doesn't 
        contain enough information to answer the question, please say so."""
        
        user_prompt = f"""Context:
{context_text}

Question: {query}

Answer:"""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    async def count_tokens(self, text: str, model_name: str = None) -> int:
        """Count tokens using tiktoken."""
        if model_name is None:
            model_name = self.default_model
        
        try:
            # Use tiktoken for accurate token counting
            encoding = tiktoken.encoding_for_model(model_name)
            return len(encoding.encode(text))
        except Exception:
            # Fallback to rough estimate
            return len(text.split()) * 1.3  # Rough estimate
    
    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get model information."""
        return self.models.get(model_name, {})
    
    async def health_check(self) -> bool:
        """Check OpenAI API health."""
        try:
            await self.client.models.list()
            return True
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return False


class LocalLLMProvider(LLMProvider):
    """Local HuggingFace LLM provider."""
    
    def __init__(self, model_manager):
        self.model_manager = model_manager
        self.default_model = "microsoft/DialoGPT-medium"
    
    async def generate_response(
        self,
        query: str,
        context: List[RetrievalResult],
        model_name: str = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stream: bool = False
    ) -> str | AsyncGenerator[str, None]:
        """Generate response using local model."""
        if model_name is None:
            model_name = self.default_model
        
        # Use existing model manager
        response = await self.model_manager.generate_response(
            query=query,
            context=context,
            model_name=model_name,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        if stream:
            # Simple streaming implementation
            for word in response.split():
                yield word + " "
                await asyncio.sleep(0.01)
        else:
            return response
    
    async def count_tokens(self, text: str, model_name: str = None) -> int:
        """Count tokens using local tokenizer."""
        if model_name is None:
            model_name = self.default_model
        
        if model_name in self.model_manager.tokenizers:
            tokenizer = self.model_manager.tokenizers[model_name]
            return len(tokenizer.encode(text))
        else:
            return len(text.split())
    
    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get model information."""
        if model_name in self.model_manager.model_usage_stats:
            stats = self.model_manager.model_usage_stats[model_name]
            return {
                "model_name": model_name,
                "loaded_at": stats["loaded_at"],
                "request_count": stats["request_count"],
                "total_tokens_generated": stats["total_tokens_generated"]
            }
        return {}
    
    async def health_check(self) -> bool:
        """Check local model health."""
        return len(self.model_manager.models) > 0


class LLMProviderManager:
    """Manages multiple LLM providers."""
    
    def __init__(self):
        self.providers: Dict[str, LLMProvider] = {}
        self.default_provider = None
    
    def register_provider(self, name: str, provider: LLMProvider, is_default: bool = False):
        """Register an LLM provider."""
        self.providers[name] = provider
        if is_default or self.default_provider is None:
            self.default_provider = name
    
    def get_provider(self, name: str = None) -> LLMProvider:
        """Get an LLM provider."""
        if name is None:
            name = self.default_provider
        
        if name not in self.providers:
            raise ValueError(f"Provider {name} not found")
        
        return self.providers[name]
    
    async def generate_response(
        self,
        query: str,
        context: List[RetrievalResult],
        provider_name: str = None,
        model_name: str = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        stream: bool = False
    ) -> str | AsyncGenerator[str, None]:
        """Generate response using specified provider."""
        provider = self.get_provider(provider_name)
        return await provider.generate_response(
            query=query,
            context=context,
            model_name=model_name,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream
        )
    
    async def count_tokens(self, text: str, provider_name: str = None, model_name: str = None) -> int:
        """Count tokens using specified provider."""
        provider = self.get_provider(provider_name)
        return await provider.count_tokens(text, model_name)
    
    def list_providers(self) -> Dict[str, Dict[str, Any]]:
        """List all registered providers."""
        return {
            name: {
                "name": name,
                "is_default": name == self.default_provider,
                "type": type(provider).__name__
            }
            for name, provider in self.providers.items()
        }
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all providers."""
        results = {}
        for name, provider in self.providers.items():
            try:
                results[name] = await provider.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = False
        
        return results
