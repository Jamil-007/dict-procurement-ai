import httpx
from config import settings


class GammaClient:
    """
    Gamma API client for generating presentations from markdown/text content.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GAMMA_API_KEY
        self.base_url = "https://api.gamma.app/api/v1"
        self.timeout = 60.0  # Gamma generation can take a while

    async def generate_presentation(self, content: str, thread_id: str) -> str:
        """
        Generate a presentation from the compiled report using Gamma API.

        Args:
            content: The compiled report content (markdown format)
            thread_id: Unique identifier for this analysis session

        Returns:
            URL to the generated Gamma presentation

        Raises:
            httpx.HTTPError: If the API request fails
            ValueError: If API key is not configured
        """
        if not self.api_key:
            raise ValueError("Gamma API key is not configured")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Gamma API endpoint for document generation from text
                response = await client.post(
                    f"{self.base_url}/docs/create-from-text",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "text": content,
                        "title": f"Procurement Analysis Report - {thread_id[:8]}",
                        "mode": "auto"  # Let Gamma auto-format the content
                    }
                )

                response.raise_for_status()
                result = response.json()

                # Gamma API returns the document URL in the response
                # The exact field name might vary based on API version
                if "url" in result:
                    return result["url"]
                elif "webUrl" in result:
                    return result["webUrl"]
                elif "docUrl" in result:
                    return result["docUrl"]
                else:
                    # Fallback: construct URL from doc ID if available
                    if "id" in result:
                        return f"https://gamma.app/docs/{result['id']}"
                    raise ValueError(f"Unexpected API response format: {result}")

            except httpx.HTTPStatusError as e:
                # Log the error and raise with more context
                error_detail = ""
                try:
                    error_detail = e.response.json()
                except:
                    error_detail = e.response.text
                raise Exception(f"Gamma API error ({e.response.status_code}): {error_detail}")
            except httpx.RequestError as e:
                raise Exception(f"Failed to connect to Gamma API: {str(e)}")

    def is_configured(self) -> bool:
        """Check if Gamma API is properly configured."""
        return bool(self.api_key)


# Global instance
gamma_client = GammaClient()
