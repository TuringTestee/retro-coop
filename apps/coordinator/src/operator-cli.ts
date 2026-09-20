import {createInterface} from 'node:readline/promises';
import {operatorRequest} from './operator.ts';

async function main() {
 const [directory,action,target,seconds,...extra]=process.argv.slice(2);
 if(!directory || extra.length || !['list','remove-room','block-address'].includes(action) || (action==='list' && target) || (action==='remove-room' && (!target || seconds)) || (action==='block-address' && (!target || !seconds)))throw Error('Usage: operator-cli.ts DIRECTORY list | remove-room ROOM_ID | block-address SUBJECT_ID SECONDS');
 const command=action==='list'?{type:'list'}:action==='remove-room'?{type:action,roomId:target}:{type:action,subjectId:target,seconds:Number(seconds)};
 const preview=await operatorRequest(directory,command);
 if(action==='list'){console.log(JSON.stringify(preview,null,2));return;}
 if(!('confirmation' in preview))throw Error('Unexpected operator response');
 console.log(preview.description);
 const input=createInterface({input:process.stdin,output:process.stdout});
 let answer:string;try {answer=await input.question('Type CONFIRM within 30 seconds to apply, or anything else to cancel: ');}finally {input.close();}
 if(answer!=='CONFIRM'){console.log('Cancelled. No change applied.');return;}
 await operatorRequest(directory,{type:'confirm',confirmation:preview.confirmation});console.log('Done.');
}
void main().catch(error=>{console.error(error instanceof Error?error.message:'Operator command failed');process.exitCode=1;});
