/* Standalone C99 integration: native Processor -> copied tensors -> generation.
 * Model paths in this small example must contain only letters/digits / _ - .
 * Provider runtime and encrypted models are external licensed dependencies.
 */
#include "qwen25_omni.h"
#include <stdio.h>
#include <string.h>
#include <ctype.h>

static int checked(int rc,const char*operation){
 if(rc){fprintf(stderr,"%s: %s\n",operation,q25o_last_error());return 0;}return 1;
}
static q25o_json_options options(const char*text){
 q25o_json_options o={sizeof(q25o_json_options),Q25O_ABI_VERSION,text,0};o.size=strlen(text);return o;
}
int main(int argc,char**argv){
 q25o_handle model=0,processor=0,batch=0,request=0;
 int failed=1;char model_json[4096];char*result=NULL;
 q25o_tensor_view tensors[2];memset(tensors,0,sizeof(tensors));
 if(argc!=2){fprintf(stderr,"usage: infer_tensors /absolute/model/root\n");return 2;}
 for(const unsigned char*p=(const unsigned char*)argv[1];*p;p++)
  if(!isalnum(*p)&&!strchr("/_.-",*p)){fprintf(stderr,"Unsupported example path character\n");return 2;}
 int n=snprintf(model_json,sizeof(model_json),"{\"model_dir\":\"%s\"}",argv[1]);
 if(n<0||(size_t)n>=sizeof(model_json)){fprintf(stderr,"Path too long\n");return 2;}
 q25o_json_options load=options(model_json);
 q25o_json_options text=options("{\"text\":\"<|im_start|>system\\nYou are a helpful assistant.<|im_end|>\\n<|im_start|>user\\nHello<|im_end|>\\n<|im_start|>assistant\\n\"}");
 q25o_json_options generation=options("{\"max_new_tokens\":32,\"do_sample\":false,\"repetition_penalty\":1.0,\"frequency_penalty\":0.0,\"presence_penalty\":0.0}");
 #define CALL(expression) do{if(!checked((expression),#expression))goto finish;}while(0)
 CALL(q25o_processor_open(&load,&processor));
 CALL(q25o_model_open(NULL,&load,&model));
 CALL(q25o_processor_process(processor,&text,NULL,0,&batch));
 CALL(q25o_batch_tensor(batch,0,&tensors[0]));
 CALL(q25o_batch_tensor(batch,1,&tensors[1]));
 CALL(q25o_request_create_tensors(model,&generation,tensors,2,&request));
 CALL(q25o_batch_close(batch));batch=0; /* request owns copies */
 CALL(q25o_request_execute(request,NULL,NULL));
 CALL(q25o_request_result(request,&result));
 printf("C_RESULT_JSON=%s\n",result);failed=0;
 finish:
 if(result)q25o_buffer_free(result);
 if(request&&!checked(q25o_request_release(request),"request_release"))failed=1;
 if(batch&&!checked(q25o_batch_close(batch),"batch_close"))failed=1;
 if(model&&!checked(q25o_model_close(model),"model_close"))failed=1;
 if(processor&&!checked(q25o_processor_close(processor),"processor_close"))failed=1;
 return failed?2:0;
}
