export const apiBaseUrl = "/api";
export const getInstallerDataUrl = `${apiBaseUrl}/installer-data`;

export const fetchInstallerData = async () => {
  try {
    const response = await fetch(getInstallerDataUrl);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Error fetching installer data:", error);
    throw error;
  }
};
