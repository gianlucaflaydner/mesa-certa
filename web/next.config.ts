import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Servidor mínimo e autocontido para a imagem Docker.
  output: "standalone",
  // O indicador de desenvolvimento cobre o canto da barra frontal nas revisões visuais.
  devIndicators: false,
};

export default nextConfig;
