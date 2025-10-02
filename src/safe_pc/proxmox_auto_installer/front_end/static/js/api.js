export const apiBaseUrl = "/api";
export const getInstallerDataUrl = `${apiBaseUrl}/installer/data`;

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

export const handleCreateIso = async (formState) => {
  try {
    const response = await fetch(`${apiBaseUrl}/installer/iso`, {
      method: "POST",
      body: JSON.stringify(formState),
      headers: {
        "Content-Type": "application/json",
      },
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    } else return await response.json();
  } catch (error) {
    console.error("Error creating ISO:", error);
    throw error;
  }
};
