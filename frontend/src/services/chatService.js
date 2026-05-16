import axios from "axios";

const API =
  "http://127.0.0.1:8000/api";

export const sendChatMessage =
  async (
    message,
    failedRules
  ) => {

    const response =
      await axios.post(
        `${API}/chat`,
        {
          message,
          failed_rules: failedRules,
        }
      );

    return response.data;
};