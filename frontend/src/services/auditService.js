import { api } from "./api";

export const runAudit = async (payload) => {

  const response = await api.post(
    "/audit/",
    payload
  );

  return response.data;
};