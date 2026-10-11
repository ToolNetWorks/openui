import type {RequestHandler} from './$types';
const proxy:RequestHandler=async ({request,params,fetch,url})=>{
 const upstream=process.env.BACKEND_URL || 'http://127.0.0.1:3004';
 const headers=new Headers(request.headers); headers.delete('host'); headers.delete('content-length'); headers.delete('connection');
 const init:RequestInit={method:request.method,headers,redirect:'manual'};
 if(request.method!=='GET'&&request.method!=='HEAD') init.body=await request.arrayBuffer();
 try {const response=await fetch(`${upstream}/api/${params.path}${url.search}`,init);
 const out=new Headers(response.headers); out.delete('content-length'); out.delete('content-encoding'); out.delete('transfer-encoding');
 return new Response(response.body,{status:response.status,headers:out});
 } catch {return Response.json({detail:'Backend không kết nối được'},{status:502});}
};
export const GET=proxy;export const POST=proxy;export const PUT=proxy;export const PATCH=proxy;export const DELETE=proxy;
